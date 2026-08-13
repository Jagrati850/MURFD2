"""
Tests for the Day 5 data tools.

No network is used: the HTTP client is replaced with fakes so both the happy path
and the "source is down" path are exercised deterministically.
"""

import httpx
import pytest

import health_tools as ht


# ---------------------------------------------------------------------------
# Fake HTTP plumbing
# ---------------------------------------------------------------------------
class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeClient:
    """Stands in for httpx.AsyncClient, returning canned payloads."""

    def __init__(self, get_payloads=None, post_payload=None, raise_exc=None):
        self._get_payloads = list(get_payloads or [])
        self._post_payload = post_payload
        self._raise = raise_exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def get(self, url, **kwargs):
        if self._raise:
            raise self._raise
        return FakeResponse(self._get_payloads.pop(0))

    async def post(self, url, **kwargs):
        if self._raise:
            raise self._raise
        return FakeResponse(self._post_payload)


NOMINATIM_HIT = [{"lat": "25.3176", "lon": "82.9739", "display_name": "Varanasi, Uttar Pradesh"}]

OVERPASS_HIT = {
    "elements": [
        {
            "type": "node",
            "lat": 25.3200,
            "lon": 82.9800,
            "tags": {"amenity": "clinic", "name": "Primary Health Centre Sigra"},
        },
        {
            "type": "node",
            "lat": 25.2680,
            "lon": 82.9910,
            "tags": {"amenity": "hospital", "name": "Sir Sunderlal Hospital", "phone": "+910000"},
        },
        {  # unnamed entries are useless to read aloud and must be dropped
            "type": "node",
            "lat": 25.3180,
            "lon": 82.9740,
            "tags": {"amenity": "clinic"},
        },
    ]
}


def _patch_client(monkeypatch, client):
    monkeypatch.setattr(ht.httpx, "AsyncClient", lambda **kwargs: client)


# ---------------------------------------------------------------------------
# Symptom triage (local ruleset)
# ---------------------------------------------------------------------------
def test_triage_red_flag_in_hinglish():
    result = ht.triage_symptoms("mujhe seene mein dard aur saans nahi aa rahi")
    assert result["triage_level"] == "red"
    assert "112" in result["recommended_action"]
    assert result["data_freshness"] == "local"


def test_triage_red_flag_in_devanagari():
    result = ht.triage_symptoms("सीने में दर्द हो रहा है")
    assert result["triage_level"] == "red"


def test_triage_amber_for_persistent_fever():
    result = ht.triage_symptoms("bukhar hai", duration_days=4)
    assert result["triage_level"] == "amber"


def test_triage_green_for_mild_cold():
    result = ht.triage_symptoms("mild cold and sore throat")
    assert result["triage_level"] == "green"


def test_triage_escalates_green_for_elderly():
    result = ht.triage_symptoms("loose motion since morning", age_band="70+")
    assert result["triage_level"] == "amber"
    assert any("higher risk" in reason for reason in result["escalation_reasons"])


def test_triage_flags_ongoing_condition():
    result = ht.triage_symptoms("body ache", ongoing_conditions="diabetes")
    assert any("diabetes" in reason for reason in result["escalation_reasons"])


def test_triage_unclear_when_nothing_matches():
    result = ht.triage_symptoms("kuch theek nahi lag raha")
    assert result["triage_level"] == "unclear"


def test_triage_requires_symptoms():
    result = ht.triage_symptoms("   ")
    assert result["status"] == "need_symptoms"
    assert result["spoken_fallback"]


def test_triage_never_names_a_medicine():
    result = ht.triage_symptoms("fever for 4 days")
    blob = " ".join(str(v) for v in result.values()).lower()
    for drug in ("paracetamol", "antibiotic", "azithromycin", "ibuprofen", "crocin"):
        assert drug not in blob


def test_every_result_is_timestamped():
    for result in (
        ht.triage_symptoms("headache"),
        ht.triage_symptoms(""),
    ):
        assert result["data_as_of"]
        assert result["data_as_of_spoken"]


# ---------------------------------------------------------------------------
# Advisory banding
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "aqi,expected",
    [(20, "good"), (80, "moderate"), (130, "unhealthy for sensitive groups"),
     (180, "unhealthy"), (260, "very unhealthy"), (400, "hazardous"), (None, "unknown")],
)
def test_aqi_bands(aqi, expected):
    assert ht._aqi_band(aqi)["band"] == expected


@pytest.mark.parametrize(
    "feels_like,expected",
    [(28, "comfortable"), (35, "caution"), (41, "high heat risk"), (46, "extreme heat risk")],
)
def test_heat_bands(feels_like, expected):
    assert ht._heat_band(feels_like)["band"] == expected


# ---------------------------------------------------------------------------
# Facility lookup — live path
# ---------------------------------------------------------------------------
async def test_facility_lookup_live_success(monkeypatch):
    _patch_client(monkeypatch, FakeClient(get_payloads=[NOMINATIM_HIT], post_payload=OVERPASS_HIT))

    result = await ht.find_health_facilities("Varanasi")

    assert result["status"] == "ok"
    assert result["data_freshness"] == "live"
    assert "OpenStreetMap" in result["source"]
    names = [f["name"] for f in result["facilities"]]
    assert "Primary Health Centre Sigra" in names
    # unnamed entries dropped, nearest first
    assert len(result["facilities"]) == 2
    assert result["facilities"][0]["distance_km"] <= result["facilities"][1]["distance_km"]
    assert result["facilities"][0]["category"] == "Primary Health Centre (PHC)"
    assert result["data_as_of_spoken"]


async def test_facility_lookup_resolves_pincode(monkeypatch):
    pin_payload = [{"PostOffice": [{"District": "Varanasi", "State": "Uttar Pradesh", "Name": "Lanka"}]}]
    client = FakeClient(get_payloads=[pin_payload, NOMINATIM_HIT], post_payload=OVERPASS_HIT)
    _patch_client(monkeypatch, client)

    result = await ht.find_health_facilities("221005")

    assert result["status"] == "ok"
    assert result["district"] == "Varanasi"
    assert result["state"] == "Uttar Pradesh"


async def test_facility_lookup_requires_a_location():
    result = await ht.find_health_facilities("")
    assert result["status"] == "need_location"
    assert result["spoken_fallback"]


async def test_facility_lookup_not_found(monkeypatch):
    _patch_client(monkeypatch, FakeClient(get_payloads=[[]]))
    result = await ht.find_health_facilities("Xyzabc Nagar")
    assert result["status"] == "not_found"
    assert "PIN code" in result["spoken_fallback"]


# ---------------------------------------------------------------------------
# Facility lookup — graceful failure path (the point of the day)
# ---------------------------------------------------------------------------
async def test_facility_lookup_falls_back_to_offline_list_on_timeout(monkeypatch):
    _patch_client(monkeypatch, FakeClient(raise_exc=httpx.TimeoutException("slow link")))

    result = await ht.find_health_facilities("Varanasi")

    assert result["status"] == "fallback"
    assert result["data_freshness"] == "local"
    assert "not live" in result["source"]
    assert "timed out" in result["reason"]
    assert result["facilities"], "offline list should still name real facilities"
    assert "offline" in result["spoken_fallback"].lower()


async def test_facility_lookup_admits_defeat_when_district_is_unknown(monkeypatch):
    _patch_client(monkeypatch, FakeClient(raise_exc=httpx.ConnectError("no network")))

    result = await ht.find_health_facilities("Chhota Gaon")

    assert result["status"] == "unavailable"
    assert result["data_freshness"] == "none"
    assert "facilities" not in result  # never invent a hospital name
    assert "108" in result["spoken_fallback"]
    assert result["helplines"]["ambulance"] == "108"


async def test_facility_lookup_when_nothing_is_mapped_nearby(monkeypatch):
    _patch_client(
        monkeypatch, FakeClient(get_payloads=[NOMINATIM_HIT], post_payload={"elements": []})
    )
    result = await ht.find_health_facilities("Varanasi", radius_km=5)
    # falls back to the offline list rather than claiming there is no care available
    assert result["status"] == "fallback"
    assert "no mapped facility within 5 km" in result["reason"]


# ---------------------------------------------------------------------------
# Heat / air-quality advisory
# ---------------------------------------------------------------------------
async def test_advisory_live_success(monkeypatch):
    weather = {"current": {"temperature_2m": 39.4, "relative_humidity_2m": 62, "apparent_temperature": 45.1}}
    air = {"current": {"pm2_5": 88.0, "pm10": 130.0, "us_aqi": 168}}
    _patch_client(monkeypatch, FakeClient(get_payloads=[NOMINATIM_HIT, weather, air]))

    result = await ht.get_health_advisory("Varanasi")

    assert result["status"] == "ok"
    assert result["data_freshness"] == "live"
    assert result["feels_like_c"] == 45.1
    assert result["heat_risk"] == "extreme heat risk"
    assert result["us_aqi"] == 168
    assert result["air_quality"] == "unhealthy"
    assert result["data_as_of_spoken"]


async def test_advisory_speaks_up_when_source_is_down(monkeypatch):
    _patch_client(monkeypatch, FakeClient(raise_exc=httpx.TimeoutException("slow link")))

    result = await ht.get_health_advisory("Varanasi")

    assert result["status"] == "unavailable"
    assert "timed out" in result["reason"]
    assert result["spoken_fallback"]
    # no invented numbers
    assert "temperature_c" not in result
    assert "us_aqi" not in result


async def test_advisory_requires_a_location():
    result = await ht.get_health_advisory("  ")
    assert result["status"] == "need_location"


# ---------------------------------------------------------------------------
# Offline dataset
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("query", ["Varanasi", "banaras", "KASHI", "kamrup", "bangalore"])
def test_offline_dataset_matches_aliases(query):
    entry = ht._fallback_facilities(query)
    assert entry and entry["facilities"]


def test_offline_dataset_declares_itself_as_local():
    meta = ht._load_fallback()["meta"]
    assert "NOT LIVE" in meta["disclosure"].upper()
    assert meta["compiled_on"]


def test_offline_dataset_has_no_invented_phone_numbers():
    for entry in ht._load_fallback()["districts"].values():
        for facility in entry["facilities"]:
            assert "phone" not in facility

