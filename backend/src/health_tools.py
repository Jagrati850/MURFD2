"""
Domain data tools for the Health Access Voice Agent — Day 5 of #VoiceForBharat.

Three lookups, each returning a structured dict the agent can speak naturally:

1. find_health_facilities — LIVE. OpenStreetMap (Nominatim geocoding + Overpass
   facility search), with an offline district list as fallback.
2. get_health_advisory    — LIVE. Open-Meteo forecast + air-quality APIs, turned
   into heat and air-quality health guidance.
3. triage_symptoms        — LOCAL. Deterministic red / amber / green ruleset.

Every result carries `status`, `source` and `data_as_of`. When a live source
fails, the result carries a `spoken_fallback` line so the agent always has
something useful to say instead of going silent or inventing an answer.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger("health_tools")

# --- Live endpoints (all free, no API key required) -------------------------
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
INDIA_POST_URL = "https://api.postalpincode.in/pincode"

# Rural connections are slow; fail fast enough that the agent can still speak.
HTTP_TIMEOUT = 8.0
OVERPASS_TIMEOUT = 20.0
USER_AGENT = "HealthAccessVoiceAgent/1.0 (VoiceForBharat challenge)"

_FALLBACK_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "health_facilities.json"
)

IST = timezone(timedelta(hours=5, minutes=30))

# Genuine, publicly listed Indian health helplines — safe to offer at any time.
NATIONAL_HELPLINES = {
    "emergency (all services)": "112",
    "ambulance": "108",
    "health helpline": "104",
    "mental health (Tele-MANAS)": "14416",
    "child helpline": "1098",
}

# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def _utc_iso() -> str:
    """Machine-readable timestamp for the moment the data was fetched."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _spoken_stamp() -> str:
    """Human timestamp the agent can read out, e.g. '11 August 2026 at 9:20 PM IST'."""
    now = datetime.now(IST)
    day = str(now.day)
    hour = str(int(now.strftime("%I")))
    return f"{day} {now.strftime('%B %Y')} at {hour}:{now.strftime('%M %p')} IST"


def _stamp() -> dict[str, str]:
    return {"data_as_of": _utc_iso(), "data_as_of_spoken": _spoken_stamp()}


def _is_pincode(value: str) -> bool:
    return bool(re.fullmatch(r"[1-9]\d{5}", value.strip()))


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres."""
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


_fallback_cache: dict[str, Any] | None = None


def _load_fallback() -> dict[str, Any]:
    """Load (and cache) the bundled offline district dataset."""
    global _fallback_cache
    if _fallback_cache is None:
        try:
            with open(_FALLBACK_PATH, encoding="utf-8") as fh:
                _fallback_cache = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read offline dataset %s: %s", _FALLBACK_PATH, exc)
            _fallback_cache = {"meta": {}, "districts": {}}
    return _fallback_cache

# ---------------------------------------------------------------------------
# Live source 1: place / pincode -> coordinates
# ---------------------------------------------------------------------------
async def _resolve_pincode(client: httpx.AsyncClient, pincode: str) -> dict | None:
    """Resolve a 6-digit Indian PIN code to district and state via India Post."""
    resp = await client.get(f"{INDIA_POST_URL}/{pincode}", timeout=HTTP_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    if not isinstance(payload, list) or not payload:
        return None
    offices = payload[0].get("PostOffice") or []
    if not offices:
        return None
    office = offices[0]
    return {
        "district": office.get("District", ""),
        "state": office.get("State", ""),
        "area": office.get("Name", ""),
    }


async def _geocode(client: httpx.AsyncClient, place: str) -> dict | None:
    """Geocode a place name to coordinates using OpenStreetMap Nominatim."""
    resp = await client.get(
        NOMINATIM_URL,
        params={"q": f"{place}, India", "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en"},
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        return None
    top = results[0]
    return {
        "lat": float(top["lat"]),
        "lon": float(top["lon"]),
        "resolved_name": top.get("display_name", place),
    }

# ---------------------------------------------------------------------------
# Live source 2: nearby health facilities (OpenStreetMap Overpass)
# ---------------------------------------------------------------------------
# Whitelisted so nothing user-supplied is ever interpolated into the query.
_FACILITY_FILTERS = {
    "hospital": "^(hospital)$",
    "clinic": "^(clinic|doctors)$",
    "pharmacy": "^(pharmacy)$",
    "any": "^(hospital|clinic|doctors)$",
}


def _classify(tags: dict[str, str]) -> str:
    """Best-effort label for an OSM entry: PHC, CHC, government or private."""
    name = (tags.get("name") or "").lower()
    if "primary health" in name or re.search(r"\bphc\b", name):
        return "Primary Health Centre (PHC)"
    if "community health" in name or re.search(r"\bchc\b", name):
        return "Community Health Centre (CHC)"
    if "district hospital" in name:
        return "District Hospital"
    if tags.get("operator:type") == "government" or "government" in name or "govt" in name:
        return "Government facility"
    amenity = tags.get("amenity", "facility")
    return {"hospital": "Hospital", "clinic": "Clinic", "doctors": "Doctor's clinic",
            "pharmacy": "Pharmacy"}.get(amenity, "Health facility")


async def _overpass_facilities(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
    facility_type: str,
    radius_km: int,
) -> list[dict]:
    """Query Overpass for facilities around a point, nearest first."""
    amenity_regex = _FACILITY_FILTERS.get(facility_type, _FACILITY_FILTERS["any"])
    radius_m = max(1, min(int(radius_km), 50)) * 1000
    query = (
        f"[out:json][timeout:{int(OVERPASS_TIMEOUT)}];"
        f'(node["amenity"~"{amenity_regex}"](around:{radius_m},{lat:.6f},{lon:.6f});'
        f'way["amenity"~"{amenity_regex}"](around:{radius_m},{lat:.6f},{lon:.6f}););'
        "out center 40;"
    )
    resp = await client.post(
        OVERPASS_URL,
        data={"data": query},
        headers={"User-Agent": USER_AGENT},
        timeout=OVERPASS_TIMEOUT,
    )
    resp.raise_for_status()
    elements = resp.json().get("elements", [])

    facilities: list[dict] = []
    for el in elements:
        tags = el.get("tags") or {}
        name = tags.get("name")
        if not name:
            continue  # an unnamed dot on a map is useless to speak aloud
        point = el.get("center") or el
        f_lat, f_lon = point.get("lat"), point.get("lon")
        if f_lat is None or f_lon is None:
            continue
        facilities.append(
            {
                "name": name,
                "category": _classify(tags),
                "distance_km": round(_haversine_km(lat, lon, f_lat, f_lon), 1),
                "phone": tags.get("phone") or tags.get("contact:phone") or "",
                "address": ", ".join(
                    part
                    for part in (
                        tags.get("addr:street"),
                        tags.get("addr:suburb"),
                        tags.get("addr:city"),
                    )
                    if part
                ),
                "opening_hours": tags.get("opening_hours", ""),
                "emergency": tags.get("emergency", ""),
            }
        )

    facilities.sort(key=lambda f: f["distance_km"])
    return facilities

# ---------------------------------------------------------------------------
# Offline fallback: bundled district list
# ---------------------------------------------------------------------------
def _fallback_facilities(location: str) -> dict | None:
    """Match a location against the bundled offline district dataset."""
    data = _load_fallback()
    districts: dict[str, Any] = data.get("districts", {})
    needle = re.sub(r"[^a-z ]", " ", location.lower()).strip()
    if not needle:
        return None

    for key, entry in districts.items():
        names = [key] + [a.lower() for a in entry.get("aliases", [])]
        if any(name in needle or needle in name for name in names):
            return {
                "district": entry.get("district", key.title()),
                "state": entry.get("state", ""),
                "facilities": entry.get("facilities", []),
                "compiled_on": data.get("meta", {}).get("compiled_on", "unknown"),
            }
    return None


def _helpline_sentence() -> str:
    return (
        "For anything urgent you can dial 112 for emergency services, "
        "108 for an ambulance, or 104 for the government health helpline."
    )

# ---------------------------------------------------------------------------
# Tool 1: nearest health facilities
# ---------------------------------------------------------------------------
async def find_health_facilities(
    location: str,
    facility_type: str = "any",
    radius_km: int = 15,
    max_results: int = 4,
) -> dict:
    """Find health facilities near an Indian town, district or PIN code."""
    location = (location or "").strip()
    if not location:
        return {
            "status": "need_location",
            "spoken_fallback": "I need a town, district or PIN code before I can look for a clinic nearby.",
            **_stamp(),
        }

    resolved: dict[str, Any] = {"district": "", "state": "", "resolved_name": location}
    failure: str | None = None

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            query = location
            if _is_pincode(location):
                pin_info = await _resolve_pincode(client, location)
                if pin_info:
                    resolved.update(district=pin_info["district"], state=pin_info["state"])
                    query = ", ".join(
                        p for p in (pin_info["area"], pin_info["district"], pin_info["state"]) if p
                    )

            geo = await _geocode(client, query)
            if geo is None:
                return {
                    "status": "not_found",
                    "location_requested": location,
                    "spoken_fallback": (
                        f"I could not find {location} on the map. Could you tell me the "
                        "district name or a six digit PIN code?"
                    ),
                    **_stamp(),
                }

            resolved["resolved_name"] = geo["resolved_name"]
            facilities = await _overpass_facilities(
                client, geo["lat"], geo["lon"], facility_type, radius_km
            )

        if facilities:
            return {
                "status": "ok",
                "data_freshness": "live",
                "source": "OpenStreetMap — Nominatim geocoding + Overpass facility search",
                "location_requested": location,
                "location_resolved": resolved["resolved_name"],
                "district": resolved["district"],
                "state": resolved["state"],
                "search_radius_km": radius_km,
                "facility_count": len(facilities),
                "facilities": facilities[: max(1, min(max_results, 8))],
                "helplines": NATIONAL_HELPLINES,
                "speaking_note": (
                    "Read out only the two or three nearest ones with their distance. "
                    "Mention that the list is community-mapped data fetched just now "
                    "and the user should phone ahead before travelling."
                ),
                **_stamp(),
            }
        failure = f"no mapped facility within {radius_km} km"

    except (httpx.TimeoutException, asyncio.TimeoutError):
        failure = "the map service timed out"
    except httpx.HTTPError as exc:
        failure = f"the map service returned an error ({type(exc).__name__})"
    except (ValueError, KeyError, TypeError) as exc:
        failure = f"the map service sent an unexpected response ({type(exc).__name__})"

    logger.warning("Live facility lookup failed for %r: %s", location, failure)

    offline = _fallback_facilities(resolved["district"] or location)
    if offline and offline["facilities"]:
        return {
            "status": "fallback",
            "data_freshness": "local",
            "source": (
                "bundled offline district list "
                f"(hand-compiled {offline['compiled_on']}, not live)"
            ),
            "reason": failure,
            "location_requested": location,
            "district": offline["district"],
            "state": offline["state"],
            "facilities": offline["facilities"][: max(1, min(max_results, 8))],
            "helplines": NATIONAL_HELPLINES,

            "spoken_fallback": (
                f"I could not reach the live health facility directory right now because "
                f"{failure}. I do have an older offline list for "
                f"{offline['district']} — let me read that instead, but please confirm "
                "the details by phone because they may have changed."
            ),
            **_stamp(),
        }

    return {
        "status": "unavailable",
        "data_freshness": "none",
        "source": "live lookup failed and no offline entry for this district",
        "reason": failure,
        "location_requested": location,
        "helplines": NATIONAL_HELPLINES,
        "spoken_fallback": (
            f"I am sorry, I could not fetch the list of nearby health centres because "
            f"{failure}. I do not want to guess names that may not exist. "
            f"{_helpline_sentence()} Shall I try the search again in a moment?"
        ),
        **_stamp(),
    }

# ---------------------------------------------------------------------------
# Tool 2: local heat and air-quality health advisory
# ---------------------------------------------------------------------------
def _aqi_band(aqi: float | None) -> dict[str, str]:
    if aqi is None:
        return {"band": "unknown", "advice": ""}
    if aqi <= 50:
        return {"band": "good", "advice": "Air is clean — outdoor activity is fine."}
    if aqi <= 100:
        return {
            "band": "moderate",
            "advice": "Air is acceptable, but people with asthma should keep their inhaler handy.",
        }
    if aqi <= 150:
        return {
            "band": "unhealthy for sensitive groups",
            "advice": "Children, elders, pregnant women and anyone with asthma or heart trouble should limit outdoor time.",
        }
    if aqi <= 200:
        return {
            "band": "unhealthy",
            "advice": "Avoid outdoor exercise, keep windows shut in the evening, and wear a well-fitting mask outside.",
        }
    if aqi <= 300:
        return {
            "band": "very unhealthy",
            "advice": "Stay indoors as much as possible. Anyone with breathing difficulty should contact a doctor early.",
        }
    return {
        "band": "hazardous",
        "advice": "Treat this as a health emergency for anyone with lung or heart disease — stay indoors and seek care if breathing worsens.",
    }


def _heat_band(feels_like_c: float | None) -> dict[str, str]:
    if feels_like_c is None:
        return {"band": "unknown", "advice": ""}
    if feels_like_c < 32:
        return {"band": "comfortable", "advice": "No special heat precautions needed."}
    if feels_like_c < 38:
        return {
            "band": "caution",
            "advice": "Drink water every hour and avoid heavy work in the afternoon sun.",
        }
    if feels_like_c < 43:
        return {
            "band": "high heat risk",
            "advice": "Stay out of direct sun between 11 a.m. and 4 p.m., use ORS if sweating heavily, and watch for dizziness or headache.",
        }
    return {
        "band": "extreme heat risk",
        "advice": "Heat stroke is a real danger — stay indoors, keep sipping ORS or salted water, and get help immediately if someone stops sweating or becomes confused.",
    }

async def _fetch_weather(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    resp = await client.get(
        OPEN_METEO_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature",
            "timezone": "auto",
        },
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("current", {})


async def _fetch_air_quality(client: httpx.AsyncClient, lat: float, lon: float) -> dict:
    resp = await client.get(
        OPEN_METEO_AQ_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current": "pm2_5,pm10,us_aqi",
            "timezone": "auto",
        },
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("current", {})


async def get_health_advisory(location: str) -> dict:
    """Fetch live heat and air-quality readings for a place and turn them into advice."""
    location = (location or "").strip()
    if not location:
        return {
            "status": "need_location",
            "spoken_fallback": "Tell me your town or district and I will check today's heat and air quality for you.",
            **_stamp(),
        }

    try:
        async with httpx.AsyncClient(follow_redirects=True) as client:
            geo = await _geocode(client, location)
            if geo is None:
                return {
                    "status": "not_found",
                    "location_requested": location,
                    "spoken_fallback": (
                        f"I could not place {location} on the map, so I cannot check the "
                        "weather there. Could you say the district name?"
                    ),
                    **_stamp(),
                }

            weather, air = await asyncio.gather(
                _fetch_weather(client, geo["lat"], geo["lon"]),
                _fetch_air_quality(client, geo["lat"], geo["lon"]),
                return_exceptions=True,
            )

        weather = weather if isinstance(weather, dict) else {}
        air = air if isinstance(air, dict) else {}
        if not weather and not air:
            raise httpx.HTTPError("both readings unavailable")

        feels_like = weather.get("apparent_temperature")
        aqi = air.get("us_aqi")
        heat = _heat_band(feels_like)
        air_band = _aqi_band(aqi)

        return {
            "status": "ok" if (weather and air) else "partial",
            "data_freshness": "live",
            "source": "Open-Meteo forecast API + Open-Meteo air-quality API",
            "location_resolved": geo["resolved_name"],
            "temperature_c": weather.get("temperature_2m"),
            "feels_like_c": feels_like,
            "humidity_percent": weather.get("relative_humidity_2m"),
            "heat_risk": heat["band"],
            "heat_advice": heat["advice"],
            "us_aqi": aqi,
            "pm2_5": air.get("pm2_5"),
            "air_quality": air_band["band"],
            "air_quality_advice": air_band["advice"],
            "speaking_note": (
                "Give the numbers plainly, one sentence each, then the single most "
                "relevant precaution. Say when the reading was taken."
            ),
            **_stamp(),
        }

    except (httpx.TimeoutException, asyncio.TimeoutError):
        reason = "the weather service timed out"
    except httpx.HTTPError as exc:
        reason = f"the weather service returned an error ({type(exc).__name__})"
    except (ValueError, KeyError, TypeError) as exc:
        reason = f"the weather service sent an unexpected response ({type(exc).__name__})"

    logger.warning("Live advisory lookup failed for %r: %s", location, reason)
    return {
        "status": "unavailable",
        "data_freshness": "none",
        "reason": reason,
        "location_requested": location,
        "spoken_fallback": (
            f"I could not fetch today's heat and air quality readings because {reason}, "
            "and I would rather not guess. General advice still holds: drink water often, "
            "avoid the afternoon sun, and if breathing feels hard, see a doctor."
        ),
        **_stamp(),
    }

# ---------------------------------------------------------------------------
# Tool 3: symptom triage (local, deterministic ruleset — never a diagnosis)
# ---------------------------------------------------------------------------
TRIAGE_RULESET_VERSION = "local-ruleset-v1"

# Red = go now. Keywords cover English, Hinglish and Devanagari because the STT
# is multilingual and users switch scripts mid-sentence.
_RED_FLAGS: list[tuple[str, list[str]]] = [
    ("chest pain or tightness", ["chest pain", "chest tight", "pain in chest", "seene mein dard", "सीने में दर्द", "छाती में दर्द"]),
    ("difficulty breathing", ["can't breathe", "cannot breathe", "breathless", "shortness of breath", "difficulty breathing", "saans nahi", "सांस लेने में तकलीफ", "सांस फूल"]),
    ("stroke warning signs", ["slurred speech", "face droop", "one side weak", "sudden numbness", "cannot speak", "लकवा", "बोलने में दिक्कत", "शरीर का एक हिस्सा सुन्न"]),
    ("loss of consciousness", ["unconscious", "fainted", "passed out", "बेहोश", "behosh"]),
    ("severe bleeding", ["heavy bleeding", "bleeding a lot", "won't stop bleeding", "बहुत खून", "खून बंद नहीं"]),
    ("seizure or fit", ["seizure", "convulsion", "fits", "मिरगी", "दौरा"]),
    ("fever with confusion or stiff neck", ["fever with confusion", "stiff neck", "delirious", "बुखार के साथ बेहोशी", "गर्दन अकड़"]),
    ("suicidal thoughts or self harm", ["suicide", "kill myself", "end my life", "self harm", "आत्महत्या", "जान देने"]),
    ("poisoning, snake bite or serious burn", ["poison", "snake bite", "snakebite", "severe burn", "जहर", "सांप ने काटा", "गंभीर जलन"]),
    ("bleeding in pregnancy", ["pregnant and bleeding", "bleeding in pregnancy", "गर्भावस्था में खून"]),
    ("severe dehydration in a baby", ["baby not passing urine", "sunken eyes", "no tears", "बच्चा पेशाब नहीं"]),
]

# Amber = see a doctor within a day or two.
_AMBER_FLAGS: list[tuple[str, list[str]]] = [
    ("persistent fever", ["fever for", "high fever", "बुखार", "bukhar", "temperature 10", "temperature 39", "temperature 40"]),
    ("blood in stool or urine", ["blood in stool", "blood in urine", "blood in vomit", "मल में खून", "पेशाब में खून"]),
    ("repeated vomiting or dehydration", ["vomiting repeatedly", "can't keep water down", "dehydrated", "उल्टी बार बार", "उल्टी हो रही"]),
    ("yellow eyes or skin (jaundice)", ["yellow eyes", "yellow skin", "jaundice", "पीलिया", "आंखें पीली"]),
    ("severe or worsening abdominal pain", ["severe stomach pain", "bad stomach pain", "abdominal pain", "पेट में तेज दर्द"]),
    ("wound that is not healing or is swollen", ["wound not healing", "pus", "swollen wound", "घाव ठीक नहीं", "मवाद"]),
    ("painful urination", ["burning urine", "painful urination", "पेशाब में जलन"]),
    ("unexplained weight loss", ["losing weight", "weight loss", "वजन कम हो"]),
    ("prolonged cough", ["cough for weeks", "coughing blood", "three weeks cough", "खांसी में खून", "पुरानी खांसी"]),
    ("rash with fever", ["rash with fever", "spots and fever", "दाने और बुखार"]),
]

# Green = self-care and monitor.
_GREEN_FLAGS: list[tuple[str, list[str]]] = [
    ("cold or blocked nose", ["cold", "runny nose", "blocked nose", "sneezing", "सर्दी", "जुकाम", "नाक बंद"]),
    ("sore throat", ["sore throat", "throat pain", "गले में दर्द", "गला खराब"]),
    ("mild headache", ["headache", "sir dard", "सिर दर्द", "सिरदर्द"]),
    ("body ache or tiredness", ["body ache", "body pain", "tired", "weakness", "बदन दर्द", "कमजोरी", "थकान"]),
    ("loose motions", ["loose motion", "diarrhea", "diarrhoea", "दस्त", "पतले दस्त"]),
    ("minor cut or bruise", ["small cut", "minor cut", "bruise", "छोटा कट", "खरोंच"]),
    ("mild acidity or gas", ["acidity", "gas", "heartburn", "गैस", "एसिडिटी"]),
]

def _match_flags(text: str, ruleset: list[tuple[str, list[str]]]) -> list[str]:
    return [flag for flag, keywords in ruleset if any(kw in text for kw in keywords)]


def _is_high_risk_age(age_band: str) -> bool:
    """Infants and elders get escalated a step; both tolerate delay badly."""
    band = (age_band or "").lower()
    very_young = ("infant", "baby", "newborn", "0-1", "0-5", "under 5")
    elderly = ("60", "65", "70", "75", "80", "elder", "senior")
    return any(token in band for token in very_young + elderly)


def triage_symptoms(
    symptoms: str,
    duration_days: int = 0,
    age_band: str = "",
    ongoing_conditions: str = "",
) -> dict:
    """Classify described symptoms into an urgency band using a local ruleset."""
    text = (symptoms or "").lower().strip()
    if not text:
        return {
            "status": "need_symptoms",
            "spoken_fallback": "Tell me what you are feeling and I will help you judge how urgent it is.",
            **_stamp(),
        }

    red = _match_flags(text, _RED_FLAGS)
    amber = _match_flags(text, _AMBER_FLAGS)
    green = _match_flags(text, _GREEN_FLAGS)

    escalations: list[str] = []

    # Duration and risk-group escalations, stated openly so the agent can explain them.
    if duration_days >= 3 and green and not amber:
        amber.append("symptoms lasting three days or more")
        escalations.append("symptoms have lasted three days or more")
    if _is_high_risk_age(age_band) and (green or amber) and not red:
        escalations.append(f"age group {age_band} is higher risk")
    conditions = (ongoing_conditions or "").lower()
    if conditions and any(
        c in conditions for c in ("diabet", "heart", "asthma", "kidney", "cancer", "pressure", "मधुमेह", "दमा")
    ):
        escalations.append(f"existing condition ({ongoing_conditions}) raises the risk")

    if red:
        level, matched = "red", red
        urgency = "emergency — seek care immediately"
        action = (
            "Stop and get emergency help now. Dial 112 for emergency services or 108 for "
            "an ambulance, or go to the nearest hospital casualty department."
        )
    elif amber or (escalations and green):
        level, matched = "amber", amber or green
        urgency = "see a doctor within 24 to 48 hours"
        action = (
            "This needs a doctor soon, not today-or-never. Visit the nearest Primary Health "
            "Centre or a doctor within a day or two, and go sooner if it gets worse."
        )
    elif green:
        level, matched = "green", green
        urgency = "self-care and watch"
        action = (
            "This usually settles with rest, fluids and light food. Watch it for two to "
            "three days, and see a doctor if it worsens or a new symptom appears."
        )
    else:
        level, matched = "unclear", []
        urgency = "not enough information"
        action = (
            "I could not match this to my checklist. Ask one or two more questions about "
            "what it feels like, how long it has lasted, and whether there is fever."
        )

    return {
        "status": "ok",
        "data_freshness": "local",
        "source": f"deterministic triage checklist, {TRIAGE_RULESET_VERSION} (offline, not a diagnosis)",
        "triage_level": level,
        "urgency": urgency,
        "recommended_action": action,
        "matched_indicators": matched,
        "escalation_reasons": escalations,
        "symptoms_reported": symptoms,
        "duration_days": duration_days,
        "helplines": NATIONAL_HELPLINES,
        "disclaimer": "This is an urgency sort, not a diagnosis. No medicine is being recommended.",
        "speaking_note": (
            "Say the urgency and the single next step in plain words. Never name a disease "
            "or a medicine. For a red result, say the emergency line first and keep it short."
        ),
        **_stamp(),
    }

