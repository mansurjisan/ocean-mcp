"""Live integration tests against real CO-OPS APIs.

Run manually: uv run python -m pytest tests/test_live.py -v -s
These tests make actual HTTP requests to NOAA CO-OPS APIs.
"""

import pytest

from coops_mcp.client import COOPSClient


@pytest.fixture
async def client():
    c = COOPSClient()
    yield c
    await c.close()


@pytest.mark.asyncio
async def test_list_water_level_stations(client):
    """List water level stations — should return many stations."""
    data = await client.fetch_metadata("stations.json", {"type": "waterlevels"})
    stations = data.get("stations", [])
    assert len(stations) > 100, f"Expected 100+ stations, got {len(stations)}"
    # Check structure
    s = stations[0]
    assert "id" in s or "stationId" in s
    assert "name" in s


@pytest.mark.asyncio
async def test_get_station_battery(client):
    """Get The Battery (8518750) station metadata."""
    data = await client.fetch_metadata("stations/8518750.json", {"units": "metric"})
    stations = data.get("stations", [data])
    station = stations[0] if isinstance(stations, list) else stations
    assert station.get("name") is not None
    assert station.get("lat") is not None or station.get("latitude") is not None


@pytest.mark.asyncio
async def test_get_water_levels_today(client):
    """Get today's water levels at The Battery."""
    data = await client.fetch_data({
        "station": "8518750",
        "product": "water_level",
        "datum": "MLLW",
        "units": "metric",
        "time_zone": "gmt",
        "date": "today",
    })
    records = data.get("data", [])
    assert len(records) > 0, "Expected water level data for today"
    assert "t" in records[0]
    assert "v" in records[0]


@pytest.mark.asyncio
async def test_get_tide_predictions(client):
    """Get tide predictions for The Battery."""
    data = await client.fetch_data({
        "station": "8518750",
        "product": "predictions",
        "datum": "MLLW",
        "units": "metric",
        "time_zone": "gmt",
        "date": "today",
    })
    records = data.get("predictions", [])
    assert len(records) > 0, "Expected tide prediction data"


@pytest.mark.asyncio
async def test_get_wind_key_west(client):
    """Get latest wind data at Key West (8724580)."""
    data = await client.fetch_data({
        "station": "8724580",
        "product": "wind",
        "units": "metric",
        "time_zone": "gmt",
        "date": "latest",
    })
    records = data.get("data", [])
    assert len(records) > 0, "Expected wind data"
    assert "s" in records[0]  # speed
    assert "d" in records[0]  # direction


@pytest.mark.asyncio
async def test_get_extreme_water_levels(client):
    """Get extreme water levels at The Battery."""
    data = await client.fetch_derived(
        "product.json",
        {"name": "extremewaterlevels", "station": "8518750", "datum": "MHHW", "units": "metric"},
    )
    assert "ExtremeWaterLevels" in data


@pytest.mark.asyncio
async def test_get_sea_level_trends(client):
    """Get sea level trends at The Battery."""
    data = await client.fetch_derived(
        "product/sealvltrends.json",
        {"station": "8518750"},
    )
    assert "SeaLvlTrends" in data


@pytest.mark.asyncio
async def test_get_datums(client):
    """Get tidal datums at The Battery."""
    data = await client.fetch_metadata(
        "stations/8518750/datums.json",
        {"units": "metric"},
    )
    datums = data.get("datums", [])
    assert len(datums) > 0, "Expected datum values"
