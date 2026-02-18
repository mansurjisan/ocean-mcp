"""Live integration tests for NHC MCP — requires internet access.

Run with: uv run pytest tests/test_live.py -v -s
"""

import pytest

from nhc_mcp.client import NHCClient
from nhc_mcp.utils import parse_hurdat2, parse_atcf_bdeck, get_arcgis_layer_id


@pytest.fixture
async def client():
    c = NHCClient()
    yield c
    await c.close()


@pytest.mark.asyncio
async def test_active_storms_endpoint(client):
    """CurrentStorms.json should return valid JSON (may be empty off-season)."""
    storms = await client.get_active_storms()
    assert isinstance(storms, list)
    # If storms exist, check structure
    for storm in storms:
        assert "id" in storm or "name" in storm


@pytest.mark.asyncio
async def test_hurdat2_atlantic_download(client):
    """Download and parse Atlantic HURDAT2 — should contain 1000+ storms."""
    text = await client.get_hurdat2("al")
    assert len(text) > 100_000  # File should be ~6.8 MB
    storms = parse_hurdat2(text)
    assert len(storms) > 1000


@pytest.mark.asyncio
async def test_hurdat2_katrina_lookup(client):
    """Find Hurricane Katrina in HURDAT2 by name and verify peak wind."""
    text = await client.get_hurdat2("al")
    storms = parse_hurdat2(text)

    # Search by name and year — storm numbering varies in HURDAT2
    katrina = None
    for s in storms:
        if s["name"] == "KATRINA" and s["id"].endswith("2005"):
            katrina = s
            break

    assert katrina is not None, "Katrina (2005) not found in HURDAT2"
    assert katrina["id"].startswith("AL")

    # Verify peak wind (should be ~150 kt)
    peak_wind = max(pt["max_wind"] for pt in katrina["track"] if pt["max_wind"] is not None)
    assert peak_wind >= 140, f"Katrina peak wind {peak_wind} kt seems too low"


@pytest.mark.asyncio
async def test_hurdat2_east_pacific_download(client):
    """Download and parse East Pacific HURDAT2."""
    text = await client.get_hurdat2("ep")
    assert len(text) > 50_000
    storms = parse_hurdat2(text)
    assert len(storms) > 500


@pytest.mark.asyncio
async def test_arcgis_forecast_layer_query(client):
    """Query the AT1 forecast points layer — should return valid response structure."""
    layer_id = get_arcgis_layer_id("AT1", "forecast_points")
    data = await client.query_arcgis_layer(layer_id)
    # Response should have 'features' key (may be empty if no active AT1 storm)
    assert "features" in data
    assert isinstance(data["features"], list)


@pytest.mark.asyncio
async def test_hurdat2_caching(client):
    """Verify that HURDAT2 data is cached after first download."""
    text1 = await client.get_hurdat2("al")
    text2 = await client.get_hurdat2("al")
    assert text1 is text2  # Should be the exact same object (cached)
