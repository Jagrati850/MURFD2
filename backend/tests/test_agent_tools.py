"""
Tests for the agent-side tool wrappers: memory chaining and safe UI mirroring.

These call the tool methods directly (no LiveKit room), so they verify the wiring
between Day 4 memory and the Day 5 lookups without a live session.
"""

import httpx
import pytest

import agent as agent_module
from test_health_tools import NOMINATIM_HIT, OVERPASS_HIT, FakeClient

import health_tools as ht


@pytest.fixture()
def health_agent():
    return agent_module.HealthAccessAgent()


@pytest.fixture()
def remembered_varanasi(monkeypatch):
    """Pretend the user told us their district on Day 4 and consented to saving it."""
    monkeypatch.setattr(
        agent_module,
        "lookup_user",
        lambda user_id: {
            "preferred_name": "Jagrati",
            "home_district": "Varanasi",
            "age_band": "60+",
            "ongoing_conditions": ["diabetes"],
        },
    )


async def test_facility_tool_reuses_remembered_district(
    health_agent, remembered_varanasi, monkeypatch
):
    monkeypatch.setattr(
        ht.httpx,
        "AsyncClient",
        lambda **kwargs: FakeClient(get_payloads=[NOMINATIM_HIT], post_payload=OVERPASS_HIT),
    )

    result = await health_agent.find_nearby_health_centre(context=None, location="")

    assert result["status"] == "ok"
    assert result["location_came_from_memory"] is True
    assert result["facilities"]


async def test_facility_tool_prefers_an_explicit_location(
    health_agent, remembered_varanasi, monkeypatch
):
    seen = {}

    async def fake_lookup(location, facility_type, radius_km):
        seen["location"] = location
        return {"status": "ok"}

    monkeypatch.setattr(agent_module, "find_health_facilities", fake_lookup)

    result = await health_agent.find_nearby_health_centre(context=None, location="Lucknow")

    assert seen["location"] == "Lucknow"
    assert result["location_came_from_memory"] is False


async def test_advisory_tool_reuses_remembered_district(
    health_agent, remembered_varanasi, monkeypatch
):
    weather = {"current": {"temperature_2m": 41.0, "relative_humidity_2m": 40, "apparent_temperature": 44.0}}
    air = {"current": {"pm2_5": 40.0, "pm10": 70.0, "us_aqi": 95}}
    monkeypatch.setattr(
        ht.httpx,
        "AsyncClient",
        lambda **kwargs: FakeClient(get_payloads=[NOMINATIM_HIT, weather, air]),
    )

    result = await health_agent.check_local_health_advisory(context=None, location="")

    assert result["status"] == "ok"
    assert result["location_came_from_memory"] is True
    assert result["heat_risk"] == "extreme heat risk"
    assert result["air_quality"] == "moderate"


async def test_triage_tool_borrows_age_and_conditions_from_memory(
    health_agent, remembered_varanasi
):
    result = await health_agent.assess_symptom_urgency(context=None, symptoms="loose motions")

    # 60+ with diabetes: a green symptom is escalated rather than waved off
    assert result["triage_level"] == "amber"
    reasons = " ".join(result["escalation_reasons"])
    assert "60+" in reasons and "diabetes" in reasons


async def test_ui_mirroring_never_breaks_a_tool(health_agent):
    """There is no LiveKit job in a test, so publishing must fail silently."""
    await health_agent._publish_to_ui("triage", {"status": "ok"})


async def test_failed_lookup_still_returns_something_speakable(
    health_agent, remembered_varanasi, monkeypatch
):
    monkeypatch.setattr(
        ht.httpx, "AsyncClient", lambda **kwargs: FakeClient(raise_exc=httpx.ConnectError("down"))
    )

    result = await health_agent.find_nearby_health_centre(context=None, location="")

    assert result["status"] == "fallback"
    assert result["spoken_fallback"]
