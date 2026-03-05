"""Live integration tests against real NWS and IEM APIs.

Run manually: uv run python -m pytest tests/test_live.py -v -s
These tests make actual HTTP requests to NWS Weather.gov and IEM APIs.
"""

import pytest

from winds_mcp.client import WindsClient


@pytest.fixture
async def client():
    """Create a WindsClient and close it after test."""
    c = WindsClient()
    yield c
    await c.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_stations_ny(client):
    """List NWS stations in New York — should return multiple stations."""
    data = await client.get_stations_by_state("NY", limit=10)
    features = data.get("features", [])
    assert len(features) > 0, "Expected at least 1 station in NY"
    props = features[0].get("properties", {})
    assert "stationIdentifier" in props


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_station_kjfk(client):
    """Get KJFK station metadata."""
    data = await client.get_station("KJFK")
    props = data.get("properties", {})
    assert props.get("stationIdentifier") == "KJFK"
    assert "Kennedy" in props.get("name", "")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_latest_observation_kjfk(client):
    """Get latest observation at KJFK — should have wind data."""
    data = await client.get_latest_observation("KJFK")
    props = data.get("properties", {})
    assert "timestamp" in props
    assert "windSpeed" in props
    assert "windDirection" in props


@pytest.mark.integration
@pytest.mark.asyncio
async def test_iem_history_jfk(client):
    """Get IEM ASOS historical data for JFK — should parse CSV correctly."""
    data = await client.get_iem_history("KJFK", "2025-01-01", "2025-01-02")
    results = data.get("results", [])
    assert len(results) > 0, "Expected IEM ASOS data for JFK"
    first = results[0]
    assert "station" in first
    assert "sknt" in first
