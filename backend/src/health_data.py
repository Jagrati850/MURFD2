"""
Health domain data layer for the Health Access Voice Agent — Day 5/10 of
#VoiceForBharat.

This module is the "tools" half of the agent: everything here retrieves or
calculates genuine health-domain data that the agent cannot invent on its own.

Data sources
------------
1. LIVE  — Nominatim (OpenStreetMap) for turning a spoken place name into
           coordinates.                      https://nominatim.openstreetmap.org
2. LIVE  — Overpass API (OpenStreetMap) for real hospitals, clinics, doctors
           and pharmacies near those coordinates.  https://overpass-api.de
3. LIVE  — Open-Meteo Air Quality API for current PM2.5 / PM10 / US AQI, which
           drives respiratory-risk advice.  https://open-meteo.com
4. LOCAL — data/fallback_facilities.json, a hand-compiled list of well-known
           government hospitals and national helplines for 24 major Indian
           districts. Used ONLY when the live sources are unreachable, and
           disclosed as local data in the README.
5. LOCAL — TRIAGE_RULES below, a deterministic red-flag / urgency rule table
           modelled on standard emergency-triage categories. This is a
           calculation, not a diagnosis, and never names a disease.

Every public function returns a dict that always carries:
    status        — "ok" | "degraded" | "unavailable"
    is_live       — True if the numbers came off the network this second
    data_source   — human-readable provenance, spoken aloud on request
    retrieved_at  — IST timestamp, so "today's reading" is never confused with
                    a stale one
    freshness     — a short spoken phrase describing 3, e.g. "checked just now"
    spoken_summary / spoken_fallback — words the agent can say directly, so a
                    dead data source is audible instead of silent or invented.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger("health_data")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",  # mirror, tried second
)
AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Nominatim's usage policy requires a real identifying User-Agent.
USER_AGENT = "HealthAccessVoiceAgent/1.0 (VoiceForBharat challenge; contact via GitHub)"

# Voice callers will not sit through a 30 second lookup. Fail fast, speak early.
# Overpass is the slow one (5-10s is normal for a city-sized radius), so it gets
# the longest leash; everything else must answer quickly or be abandoned.
GEOCODE_TIMEOUT = 6.0
OVERPASS_TIMEOUT = 22.0
AIR_QUALITY_TIMEOUT = 6.0

# Overpass returns at most this many elements per query, so a full page means
# "at least this many exist" rather than an exact count.
OVERPASS_RESULT_CAP = 60

IST = timezone(timedelta(hours=5, minutes=30))  # India has no DST, so a fixed
#                                                 offset is safer than tzdata.

_FALLBACK_PATH = Path(__file__).resolve().parent.parent / "data" / "fallback_facilities.json"

# In-process TTL caches. Nominatim asks for at most 1 request/second, and a
# caller often asks two questions about the same town in one breath.
_GEOCODE_CACHE: dict[str, tuple[float, dict]] = {}
_GEOCODE_TTL = 24 * 60 * 60  # place coordinates do not move
_AIR_CACHE: dict[str, tuple[float, dict]] = {}
_AIR_TTL = 30 * 60  # the upstream model publishes hourly
_FACILITY_CACHE: dict[str, tuple[float, dict]] = {}
_FACILITY_TTL = 60 * 60

# ---------------------------------------------------------------------------
# Timestamps and freshness
# ---------------------------------------------------------------------------
def _now_ist() -> datetime:
    return datetime.now(IST)


def _stamp(moment: Optional[datetime] = None) -> str:
    """Format a moment the way a person would say it out loud."""
    moment = moment or _now_ist()
    hour = moment.hour % 12 or 12
    ampm = "AM" if moment.hour < 12 else "PM"
    return f"{moment.day} {moment:%B %Y}, {hour}:{moment:%M} {ampm} IST"


def _freshness(is_live: bool, source_time: Optional[datetime] = None) -> str:
    """A short spoken phrase telling the listener how old this number is."""
    if not is_live:
        return "from my offline reference list, not a live reading"
    if source_time is None:
        return "checked live just now"

    age_minutes = int((_now_ist() - source_time).total_seconds() // 60)
    if age_minutes <= 1:
        return "checked live just now"
    if age_minutes < 60:
        return f"a live reading from {age_minutes} minutes ago"
    hours = age_minutes // 60
    if hours < 24:
        return f"a live reading from about {hours} hour{'s' if hours > 1 else ''} ago"
    return f"a live reading from {hours // 24} day(s) ago — treat it as out of date"


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------
def _cache_get(cache: dict, key: str, ttl: float) -> Optional[dict]:
    entry = cache.get(key)
    if entry is None:
        return None
    stored_at, value = entry
    if time.time() - stored_at > ttl:
        cache.pop(key, None)
        return None
    return value


def _cache_put(cache: dict, key: str, value: dict) -> None:
    cache[key] = (time.time(), value)


# ---------------------------------------------------------------------------
# Network and geometry helpers
# ---------------------------------------------------------------------------
async def _get_json(
    url: str,
    params: dict[str, Any],
    timeout: float,
    attempts: int = 2,
) -> Optional[Any]:
    """GET JSON, returning None on any failure. Never raises at the caller."""
    last_error: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            async with httpx.AsyncClient(
                timeout=timeout, headers={"User-Agent": USER_AGENT}
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except Exception as exc:  # network, timeout, HTTP status, bad JSON
            last_error = exc
            if attempt + 1 < attempts:
                await asyncio.sleep(0.4 * (attempt + 1))
    logger.warning("GET %s failed after %d attempts: %s", url, attempts, last_error)
    return None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return round(radius * 2 * math.asin(math.sqrt(a)), 2)


def _load_fallback() -> dict:
    """Read the bundled offline dataset. Returns {} if the file is missing."""
    try:
        with open(_FALLBACK_PATH, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception as exc:
        logger.error("Offline fallback dataset unreadable at %s: %s", _FALLBACK_PATH, exc)
        return {}


def helplines() -> dict[str, str]:
    """National health helpline numbers from the offline dataset."""
    return _load_fallback().get("national_helplines", {"emergency_all_services": "112"})


# ---------------------------------------------------------------------------
# 1. Geocoding — spoken place name to coordinates
# ---------------------------------------------------------------------------
async def geocode_place(place: str) -> dict:
    """Resolve an Indian place name to coordinates.

    Tries live Nominatim first, then the offline district table. The offline
    table only covers 24 large districts, so a miss there is reported honestly
    rather than guessed at.
    """
    query = (place or "").strip()
    if not query:
        return {"status": "unavailable", "reason": "no place given"}

    cache_key = query.lower()
    cached = _cache_get(_GEOCODE_CACHE, cache_key, _GEOCODE_TTL)
    if cached:
        return cached

    # Bias the search to India so "Hyderabad" is not resolved to Pakistan.
    payload = await _get_json(
        NOMINATIM_URL,
        {
            "q": query if "india" in query.lower() else f"{query}, India",
            "format": "json",
            "limit": 1,
            "countrycodes": "in",
            "addressdetails": 1,
        },
        GEOCODE_TIMEOUT,
    )

    if isinstance(payload, list) and payload:
        hit = payload[0]
        result = {
            "status": "ok",
            "is_live": True,
            "place": hit.get("display_name", query).split(",")[0].strip(),
            "display_name": hit.get("display_name", query),
            "lat": float(hit["lat"]),
            "lon": float(hit["lon"]),
            "data_source": "live: OpenStreetMap Nominatim geocoder",
        }
        _cache_put(_GEOCODE_CACHE, cache_key, result)
        return result

    return _geocode_offline(query)


def _geocode_offline(query: str) -> dict:
    """Match a place against the bundled district table (substring, both ways)."""
    districts = _load_fallback().get("districts", {})
    needle = query.lower().replace(",", " ").split(" india")[0].strip()

    for key, entry in districts.items():
        display = entry.get("display_name", key).lower()
        if key in needle or needle in key or display in needle or needle in display:
            return {
                "status": "degraded",
                "is_live": False,
                "place": entry.get("display_name", key.title()),
                "display_name": entry.get("display_name", key.title()),
                "lat": entry["lat"],
                "lon": entry["lon"],
                "district_key": key,
                "data_source": "local: bundled district table (live geocoder unreachable)",
            }

    return {
        "status": "unavailable",
        "is_live": False,
        "reason": "place not found live or offline",
        "place": query,
        "spoken_fallback": (
            f"I could not find {query} on the map just now, and it is not in my offline list "
            "either. Could you tell me the nearest large town or district instead?"
        ),
    }


# ---------------------------------------------------------------------------
# 2. Facility finder — real hospitals, clinics and pharmacies nearby
# ---------------------------------------------------------------------------
# Maps the words a caller actually uses onto OpenStreetMap amenity tags.
FACILITY_KINDS: dict[str, tuple[str, str]] = {
    "hospital": ("^(hospital)$", "hospital"),
    "clinic": ("^(clinic|doctors)$", "clinic or doctor's chamber"),
    "doctor": ("^(clinic|doctors)$", "clinic or doctor's chamber"),
    "pharmacy": ("^(pharmacy|chemist)$", "pharmacy"),
    "medicine": ("^(pharmacy|chemist)$", "pharmacy"),
    "any": ("^(hospital|clinic|doctors)$", "health facility"),
}


async def find_facilities(
    place: str,
    facility_type: str = "any",
    radius_km: float = 8.0,
    limit: int = 5,
) -> dict:
    """Find real health facilities near a place, live from OpenStreetMap.

    Falls back to the bundled government-hospital list, then to helpline
    numbers, so there is always something useful to say.
    """
    kind = (facility_type or "any").strip().lower()
    pattern, spoken_kind = FACILITY_KINDS.get(kind, FACILITY_KINDS["any"])
    radius_km = max(1.0, min(float(radius_km or 8.0), 25.0))
    limit = max(1, min(int(limit or 5), 8))

    located = await geocode_place(place)
    if located.get("status") == "unavailable":
        return _facilities_unavailable(place, located.get("spoken_fallback"))

    cache_key = f"{located['lat']:.3f},{located['lon']:.3f}|{pattern}|{radius_km}"
    cached = _cache_get(_FACILITY_CACHE, cache_key, _FACILITY_TTL)
    if cached:
        refreshed = dict(cached)
        refreshed["freshness"] = "from a live lookup made within the last hour"
        return refreshed

    found = await _overpass_search(located, pattern, radius_km)

    if found:
        result = _build_facility_result(located, found, spoken_kind, radius_km, limit)
        _cache_put(_FACILITY_CACHE, cache_key, result)
        return result

    return _facilities_offline(place, located, spoken_kind)


async def _overpass_search(located: dict, pattern: str, radius_km: float) -> list[dict]:
    """Query Overpass for tagged health amenities. Returns [] on any failure."""
    lat, lon = located["lat"], located["lon"]
    radius_m = int(radius_km * 1000)
    query = (
        f"[out:json][timeout:{int(OVERPASS_TIMEOUT)}];"
        f'(node["amenity"~"{pattern}"](around:{radius_m},{lat},{lon});'
        f'way["amenity"~"{pattern}"](around:{radius_m},{lat},{lon}););'
        f"out center {OVERPASS_RESULT_CAP};"
    )

    for endpoint in OVERPASS_URLS:
        try:
            async with httpx.AsyncClient(
                timeout=OVERPASS_TIMEOUT, headers={"User-Agent": USER_AGENT}
            ) as client:
                response = await client.post(endpoint, content=query.encode("utf-8"))
                response.raise_for_status()
                elements = response.json().get("elements", [])
        except Exception as exc:
            logger.warning("Overpass endpoint %s failed: %s", endpoint, exc)
            continue

        facilities: list[dict] = []
        for element in elements:
            tags = element.get("tags", {}) or {}
            name = tags.get("name") or tags.get("name:en")
            if not name:
                continue  # an unnamed dot on a map is useless to speak aloud
            centre = element.get("center") or element
            e_lat, e_lon = centre.get("lat"), centre.get("lon")
            if e_lat is None or e_lon is None:
                continue
            facilities.append(
                {
                    "name": name,
                    "kind": tags.get("healthcare") or tags.get("amenity", ""),
                    "distance_km": _haversine_km(lat, lon, e_lat, e_lon),
                    "address": _short_address(tags),
                    "phone": tags.get("phone") or tags.get("contact:phone") or "",
                    "emergency": tags.get("emergency", ""),
                    "operator": tags.get("operator", ""),
                }
            )

        if facilities:
            facilities.sort(key=lambda f: f["distance_km"])
            return facilities
    return []


def _short_address(tags: dict) -> str:
    """Build a spoken-length address from OSM address tags."""
    parts = [
        tags.get("addr:street"),
        tags.get("addr:suburb") or tags.get("addr:neighbourhood"),
        tags.get("addr:city"),
    ]
    return ", ".join(p for p in parts if p)


def _build_facility_result(
    located: dict,
    facilities: list[dict],
    spoken_kind: str,
    radius_km: float,
    limit: int,
) -> dict:
    """Assemble the live result, including words the agent can speak directly."""
    top = facilities[:limit]
    place = located.get("place", "your area")
    is_live_location = located.get("is_live", False)

    lines = []
    for index, facility in enumerate(top, start=1):
        detail = f"{index}. {facility['name']}, about {facility['distance_km']} kilometres away"
        if facility["emergency"] == "yes":
            detail += ", listed as having emergency services"
        lines.append(detail)

    # The Overpass query caps its own output, so a full page means "at least".
    capped = len(facilities) >= OVERPASS_RESULT_CAP
    count_phrase = f"more than {OVERPASS_RESULT_CAP}" if capped else str(len(facilities))

    summary = (
        f"I found {count_phrase} {spoken_kind}{'s' if capped or len(facilities) != 1 else ''} "
        f"within {radius_km:g} kilometres of {place}. The closest ones are: "
        + "; ".join(lines)
        + "."
    )

    return {
        "status": "ok" if is_live_location else "degraded",
        "is_live": True,
        "place": place,
        "search_radius_km": radius_km,
        "total_found": len(facilities),
        "result_list_truncated": capped,
        "facilities": top,
        "data_source": (
            "live: OpenStreetMap Overpass API"
            if is_live_location
            else "live: OpenStreetMap Overpass API (location from offline district table)"
        ),
        "retrieved_at": _stamp(),
        "freshness": _freshness(True),
        "caveat": "OpenStreetMap is community-maintained, so phone numbers and opening hours may be out of date. Ask the caller to phone ahead.",
        "spoken_summary": summary,
    }


def _facilities_offline(place: str, located: dict, spoken_kind: str) -> dict:
    """Live map search failed — serve the bundled government-hospital list."""
    fallback = _load_fallback()
    districts = fallback.get("districts", {})
    key = located.get("district_key")

    if not key:
        needle = (located.get("place") or place or "").lower()
        for candidate, entry in districts.items():
            if candidate in needle or needle in candidate:
                key = candidate
                break

    if key and key in districts:
        entry = districts[key]
        names = [f["name"] for f in entry["facilities"][:3]]
        return {
            "status": "degraded",
            "is_live": False,
            "place": entry["display_name"],
            "facilities": entry["facilities"],
            "data_source": f"local: bundled district hospital list, compiled {fallback.get('_meta', {}).get('compiled_on', 'earlier')}",
            "retrieved_at": _stamp(),
            "freshness": _freshness(False),
            "helplines": fallback.get("national_helplines", {}),
            "spoken_summary": (
                f"My live map service is not responding right now, so I am reading from my "
                f"offline list instead — this is not a live result. In {entry['display_name']}, "
                f"the main government hospitals are {', '.join(names)}. "
                "For an ambulance you can dial one-zero-eight, or one-one-two for any emergency."
            ),
        }

    return _facilities_unavailable(place, None)


def _facilities_unavailable(place: str, reason: Optional[str]) -> dict:
    """Nothing worked. Still say something useful — never go silent."""
    numbers = helplines()
    return {
        "status": "unavailable",
        "is_live": False,
        "place": place,
        "facilities": [],
        "data_source": "none — live lookup failed and this place is not in the offline list",
        "retrieved_at": _stamp(),
        "helplines": numbers,
        "spoken_fallback": reason
        or (
            f"I am sorry — I could not reach my facility directory for {place} just now, and I "
            "do not want to guess at a hospital name. Please dial one-one-two for emergency "
            "services, or one-zero-eight for an ambulance, and they will direct you to the "
            "nearest centre. Shall I try again in a moment?"
        ),
    }


# ---------------------------------------------------------------------------
# 3. Air quality — live respiratory-risk data
# ---------------------------------------------------------------------------
# US AQI bands with the advice that actually changes a caller's day.
AQI_BANDS: tuple[tuple[int, str, str], ...] = (
    (50, "good", "The air is clean. Outdoor activity is fine for everyone."),
    (100, "moderate", "The air is acceptable, but if you have asthma or a lung condition you may notice mild irritation."),
    (150, "unhealthy for sensitive groups", "Children, older adults, pregnant women and anyone with asthma or heart disease should cut down on outdoor exertion today."),
    (200, "unhealthy", "Everyone may feel some effect. Avoid outdoor exercise, keep windows shut in the afternoon, and wear a well-fitting mask outside."),
    (300, "very unhealthy", "This is a health alert level. Stay indoors as much as you can, avoid all outdoor exertion, and use a mask if you must go out."),
    (10_000, "hazardous", "This is an emergency air quality level. Stay indoors, keep windows closed, and seek medical help immediately if breathing becomes difficult."),
)


def _aqi_band(aqi: float) -> tuple[str, str]:
    for ceiling, label, advice in AQI_BANDS:
        if aqi <= ceiling:
            return label, advice
    return AQI_BANDS[-1][1], AQI_BANDS[-1][2]


async def get_air_quality(place: str) -> dict:
    """Current air quality for a place, live from the Open-Meteo model."""
    located = await geocode_place(place)
    if located.get("status") == "unavailable":
        return {
            "status": "unavailable",
            "is_live": False,
            "place": place,
            "retrieved_at": _stamp(),
            "spoken_fallback": located.get("spoken_fallback")
            or f"I could not find {place} on the map, so I cannot check its air quality.",
        }

    cache_key = f"{located['lat']:.2f},{located['lon']:.2f}"
    cached = _cache_get(_AIR_CACHE, cache_key, _AIR_TTL)
    if cached:
        return cached

    payload = await _get_json(
        AIR_QUALITY_URL,
        {
            "latitude": located["lat"],
            "longitude": located["lon"],
            "current": "pm2_5,pm10,us_aqi,nitrogen_dioxide,ozone",
            "timezone": "Asia/Kolkata",
        },
        AIR_QUALITY_TIMEOUT,
    )

    if not isinstance(payload, dict) or "current" not in payload:
        return _air_unavailable(located.get("place", place))

    return _build_air_result(located, payload, cache_key)


def _build_air_result(located: dict, payload: dict, cache_key: str) -> dict:
    current = payload["current"]
    aqi = current.get("us_aqi")
    pm25 = current.get("pm2_5")
    pm10 = current.get("pm10")

    if aqi is None:
        return _air_unavailable(located.get("place", "that area"))

    band, advice = _aqi_band(float(aqi))
    place = located.get("place", "that area")

    # The model publishes hourly; report the reading's own timestamp, not ours.
    reading_time: Optional[datetime] = None
    try:
        reading_time = datetime.fromisoformat(current["time"]).replace(tzinfo=IST)
    except Exception:
        pass

    result = {
        "status": "ok",
        "is_live": True,
        "place": place,
        "us_aqi": round(float(aqi)),
        "aqi_band": band,
        "pm2_5_ug_m3": pm25,
        "pm10_ug_m3": pm10,
        "nitrogen_dioxide_ug_m3": current.get("nitrogen_dioxide"),
        "ozone_ug_m3": current.get("ozone"),
        "health_advice": advice,
        "data_source": "live: Open-Meteo Air Quality API (CAMS model)",
        "reading_time": _stamp(reading_time) if reading_time else _stamp(),
        "retrieved_at": _stamp(),
        "freshness": _freshness(True, reading_time),
        "spoken_summary": (
            f"Right now in {place} the air quality index is {round(float(aqi))}, which counts as "
            f"{band}. Fine particulate matter, PM two point five, is at {pm25} micrograms per "
            f"cubic metre. {advice} This is {_freshness(True, reading_time)}."
        ),
    }
    _cache_put(_AIR_CACHE, cache_key, result)
    return result


def _air_unavailable(place: str) -> dict:
    return {
        "status": "unavailable",
        "is_live": False,
        "place": place,
        "retrieved_at": _stamp(),
        "data_source": "none — the live air quality service did not respond",
        "spoken_fallback": (
            f"I could not get a live air quality reading for {place} just now — the monitoring "
            "service is not responding, and I would rather not invent a number. In general, if "
            "you are coughing or wheezing, keep windows shut in the afternoon and wear a mask "
            "outdoors. Would you like me to try again?"
        ),
    }


# ---------------------------------------------------------------------------
# 4. Symptom triage — a deterministic urgency calculation
# ---------------------------------------------------------------------------
# This is a LOCAL rule table, modelled on standard emergency red-flag triage
# categories. It decides HOW FAST someone should be seen. It never names a
# disease, never suggests a medicine, and is not a diagnosis. Keywords are
# listed in English, Hinglish and Devanagari because callers speak all three.
LEVEL_ORDER = ("self_care", "routine", "urgent", "emergency")

TRIAGE_RULES: tuple[dict[str, Any], ...] = (
    # ---- EMERGENCY: call 112 / 108 now ----------------------------------
    {"level": "emergency", "label": "chest pain or pressure", "keywords": (
        "chest pain", "chest tightness", "chest pressure", "seene mein dard",
        "chhati mein dard", "सीने में दर्द", "छाती में दर्द", "सीने में जकड़न")},
    {"level": "emergency", "label": "difficulty breathing", "keywords": (
        "can't breathe", "cannot breathe", "difficulty breathing", "breathless",
        "shortness of breath", "gasping", "saans lene mein takleef", "dam ghut",
        "सांस लेने में तकलीफ", "सांस फूल", "दम घुट", "श्वास लेने में कठिनाई")},
    {"level": "emergency", "label": "possible stroke signs", "keywords": (
        "slurred speech", "face drooping", "one side weakness", "sudden numbness",
        "cannot speak", "sudden confusion", "worst headache", "thunderclap headache",
        "lakwa", "लकवा", "बोलने में दिक्कत", "अचानक सुन्न")},
    {"level": "emergency", "label": "loss of consciousness", "keywords": (
        "unconscious", "fainted", "passed out", "not responding", "behosh",
        "बेहोश", "होश नहीं")},
    {"level": "emergency", "label": "severe bleeding", "keywords": (
        "heavy bleeding", "severe bleeding", "bleeding a lot", "won't stop bleeding",
        "vomiting blood", "blood in vomit", "coughing blood", "khoon beh",
        "खून बह", "खून की उल्टी", "खून थूक")},
    {"level": "emergency", "label": "seizure or fits", "keywords": (
        "seizure", "convulsion", "fits", "mirgi", "मिर्गी", "दौरा", "ऐंठन")},
    {"level": "emergency", "label": "poisoning, snake bite or major burn", "keywords": (
        "poison", "snake bite", "snakebite", "overdose", "swallowed chemical",
        "major burn", "severe burn", "electric shock", "saanp ne kata",
        "सांप ने काटा", "ज़हर", "जहर", "गंभीर जलन")},
    {"level": "emergency", "label": "thoughts of self-harm", "keywords": (
        "suicide", "suicidal", "kill myself", "end my life", "self harm",
        "hurt myself", "आत्महत्या", "जान देना", "खुद को नुकसान")},
    {"level": "emergency", "label": "fever with confusion or stiff neck", "keywords": (
        "fever with confusion", "delirium", "stiff neck", "not making sense",
        "बुखार के साथ बेहोशी", "गर्दन अकड़")},
    {"level": "emergency", "label": "bleeding or severe pain in pregnancy", "keywords": (
        "pregnant and bleeding", "bleeding in pregnancy", "labour pain",
        "water broke", "गर्भावस्था में खून", "प्रसव पीड़ा")},
    # ---- URGENT: be seen today ------------------------------------------
    {"level": "urgent", "label": "animal or dog bite", "keywords": (
        "dog bite", "animal bite", "monkey bite", "cat bite", "kutte ne kata",
        "कुत्ते ने काटा", "जानवर ने काटा")},
    {"level": "urgent", "label": "high or persistent fever", "keywords": (
        "high fever", "very high temperature", "103", "104", "tez bukhar",
        "तेज़ बुखार", "तेज बुखार", "बुखार उतर नहीं")},
    {"level": "urgent", "label": "repeated vomiting or signs of dehydration", "keywords": (
        "vomiting repeatedly", "cannot keep water down", "severe dehydration",
        "no urine", "sunken eyes", "बार बार उल्टी", "पानी नहीं रुक", "निर्जलीकरण")},
    {"level": "urgent", "label": "sudden vision problem or eye injury", "keywords": (
        "vision loss", "cannot see", "eye injury", "double vision",
        "आंख में चोट", "दिखाई नहीं")},
    {"level": "urgent", "label": "jaundice or dark urine", "keywords": (
        "jaundice", "yellow eyes", "yellow skin", "dark urine", "peelia",
        "पीलिया", "आंखें पीली")},
    {"level": "urgent", "label": "severe abdominal pain", "keywords": (
        "severe stomach pain", "severe abdominal pain", "hard stomach",
        "पेट में तेज़ दर्द", "पेट सख्त")},
    {"level": "urgent", "label": "fever with rash or bleeding gums", "keywords": (
        "fever with rash", "bleeding gums", "nosebleed with fever", "platelet",
        "dengue", "डेंगू", "मसूड़ों से खून")},
    {"level": "urgent", "label": "blood in urine or stool", "keywords": (
        "blood in urine", "blood in stool", "black stool",
        "पेशाब में खून", "मल में खून")},
    # ---- ROUTINE: see a doctor in the next day or two --------------------
    {"level": "routine", "label": "cough lasting more than two weeks", "keywords": (
        "cough for two weeks", "cough for a month", "long standing cough",
        "chronic cough", "लगातार खांसी", "पुरानी खांसी")},
    {"level": "routine", "label": "unexplained weight loss or night sweats", "keywords": (
        "losing weight", "weight loss", "night sweats", "वजन कम हो रहा",
        "रात में पसीना")},
    {"level": "routine", "label": "fever for two to three days", "keywords": (
        "fever", "temperature", "bukhar", "बुखार", "ज्वर")},
    {"level": "routine", "label": "loose motions or diarrhoea", "keywords": (
        "diarrhoea", "diarrhea", "loose motion", "dast", "दस्त", "पतला मल")},
    {"level": "routine", "label": "persistent skin rash or wound", "keywords": (
        "rash", "skin infection", "wound not healing", "boil", "खुजली",
        "चकत्ते", "घाव")},
    {"level": "routine", "label": "ear pain or discharge", "keywords": (
        "ear pain", "ear discharge", "कान में दर्द", "कान से पानी")},
    # ---- SELF CARE: rest, fluids, watch for change -----------------------
    {"level": "self_care", "label": "common cold symptoms", "keywords": (
        "runny nose", "blocked nose", "sneezing", "common cold", "sore throat",
        "जुकाम", "नाक बह", "छींक", "गले में खराश")},
    {"level": "self_care", "label": "mild headache", "keywords": (
        "mild headache", "headache", "sar dard", "सिर दर्द", "सरदर्द")},
    {"level": "self_care", "label": "body ache or tiredness", "keywords": (
        "body ache", "body pain", "tired", "fatigue", "weakness",
        "बदन दर्द", "थकान", "कमजोरी")},
    {"level": "self_care", "label": "mild acidity or gas", "keywords": (
        "acidity", "gas", "indigestion", "heartburn", "एसिडिटी", "गैस",
        "अपच", "जलन")},
)

# Conditions that make the same symptom more dangerous. Purely additive.
RISK_MODIFIERS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("infant", "newborn", "baby", "0-1", "under 1", "नवजात", "शिशु"),
     "the patient is an infant, where illness can worsen very quickly"),
    (("60+", "65+", "70+", "elderly", "senior", "बुजुर्ग"),
     "the patient is elderly, so symptoms are easy to underestimate"),
    (("pregnant", "pregnancy", "गर्भवती", "गर्भावस्था"),
     "the patient is pregnant, which raises the threshold for waiting"),
    (("diabetes", "diabetic", "sugar", "मधुमेह", "शुगर"),
     "diabetes slows healing and hides infection"),
    (("asthma", "copd", "tb", "tuberculosis", "अस्थमा", "दमा", "टीबी"),
     "an existing lung condition makes breathing symptoms more serious"),
    (("heart", "cardiac", "hypertension", "bp", "दिल", "हृदय", "रक्तचाप"),
     "an existing heart or blood pressure condition raises the risk"),
    (("cancer", "chemotherapy", "hiv", "immunocompromised", "कैंसर"),
     "a weakened immune system makes infections more dangerous"),
)

ACTION_BY_LEVEL: dict[str, dict[str, str]] = {
    "emergency": {
        "act_within": "immediately — right now",
        "action": "Call 112 for emergency services or 108 for an ambulance, or get to the nearest hospital emergency department without waiting.",
    },
    "urgent": {
        "act_within": "today, within the next few hours",
        "action": "See a doctor today at your nearest hospital, clinic or primary health centre. Do not wait for tomorrow.",
    },
    "routine": {
        "act_within": "within the next one to two days",
        "action": "Book a visit to a doctor or your nearest primary health centre in the next day or two, and keep watching for any of the warning signs.",
    },
    "self_care": {
        "act_within": "no rush, but keep watching",
        "action": "Rest, drink plenty of fluids, and eat lightly. If it has not started improving in three days, or if it gets worse, see a doctor.",
    },
}

def triage_symptoms(
    symptoms: str,
    age_band: str = "",
    duration_days: float = 0.0,
    ongoing_conditions: str = "",
) -> dict:
    """Calculate how urgently someone should be seen, from a local rule table.

    Deterministic and offline — it works even when every network call fails.
    Returns an urgency level, the red flags that produced it, and words the
    agent can speak. It deliberately does not name a disease or a medicine.
    """
    haystack = (symptoms or "").lower()
    if not haystack.strip():
        return {
            "status": "unavailable",
            "reason": "no symptoms described",
            "spoken_fallback": "Could you tell me a little more about what you are feeling?",
        }

    context = f"{age_band or ''} {ongoing_conditions or ''}".lower()

    matched: list[dict[str, str]] = []
    for rule in TRIAGE_RULES:
        for keyword in rule["keywords"]:
            if keyword.lower() in haystack:
                matched.append({"level": rule["level"], "label": rule["label"]})
                break

    risk_notes = [note for keys, note in RISK_MODIFIERS if any(k in context or k in haystack for k in keys)]

    level = _highest_level(matched)

    # A long-running complaint is escalated one step; a fever that will not
    # break after four days is a different question from a fever this morning.
    escalated_for_duration = False
    try:
        days = float(duration_days or 0)
    except (TypeError, ValueError):
        days = 0.0
    if days >= 4 and level in ("self_care", "routine"):
        level = "urgent" if level == "routine" else "routine"
        escalated_for_duration = True

    # A vulnerable patient is escalated one step, but never above urgent —
    # only a real red flag can declare an emergency.
    escalated_for_risk = False
    if risk_notes and level in ("self_care", "routine"):
        level = LEVEL_ORDER[LEVEL_ORDER.index(level) + 1]
        escalated_for_risk = True

    return _build_triage_result(
        symptoms, matched, risk_notes, level, days,
        escalated_for_duration, escalated_for_risk,
    )


def _highest_level(matched: list[dict[str, str]]) -> str:
    """Most severe matched level wins; nothing matched means unclassified."""
    if not matched:
        return "routine"
    return max((m["level"] for m in matched), key=LEVEL_ORDER.index)


def _build_triage_result(
    symptoms: str,
    matched: list[dict[str, str]],
    risk_notes: list[str],
    level: str,
    days: float,
    escalated_for_duration: bool,
    escalated_for_risk: bool,
) -> dict:
    plan = ACTION_BY_LEVEL[level]
    red_flags = [m["label"] for m in matched if m["level"] == "emergency"]
    all_flags = [m["label"] for m in matched]

    reasons: list[str] = []
    if all_flags:
        reasons.append("what you described matches: " + ", ".join(all_flags))
    else:
        reasons.append("nothing you described matches a known warning sign, so I am being cautious")
    if escalated_for_duration:
        reasons.append(f"it has been going on for {days:g} days, which moves it up a step")
    if escalated_for_risk and risk_notes:
        reasons.append(risk_notes[0])

    if level == "emergency":
        spoken = (
            "Please listen carefully. "
            + (f"{', '.join(red_flags).capitalize()} needs urgent medical attention. " if red_flags else "")
            + "Call one-one-two for emergency services, or one-zero-eight for an ambulance, "
            "or go to the nearest hospital emergency department right now. Do not wait, and "
            "do not drive yourself. Would you like me to find the closest hospital to you?"
        )
    else:
        spoken = (
            f"From what you have told me, this looks like something to handle "
            f"{plan['act_within']}. {plan['action']} I am saying that because "
            f"{reasons[0]}. Remember, I am not a doctor and this is general guidance, "
            "not a diagnosis."
        )

    return {
        "status": "ok",
        "is_live": False,
        "urgency_level": level,
        "act_within": plan["act_within"],
        "recommended_action": plan["action"],
        "matched_signs": all_flags,
        "emergency_red_flags": red_flags,
        "risk_factors": risk_notes,
        "duration_days": days,
        "symptoms_assessed": symptoms,
        "data_source": "local: built-in red-flag triage rule table (offline, deterministic)",
        "assessed_at": _stamp(),
        "freshness": "calculated just now from a fixed offline rule table",
        "disclaimer": "This is an urgency estimate, not a diagnosis. No disease is named and no medicine is recommended.",
        "helplines": helplines(),
        "spoken_summary": spoken,
    }
