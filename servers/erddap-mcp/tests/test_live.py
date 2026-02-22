"""Live integration tests against real ERDDAP servers.

Run manually: uv run pytest tests/test_live.py -v -s
These tests make actual HTTP requests to public ERDDAP servers.
"""

import pytest

from erddap_mcp.client import ERDDAPClient
from erddap_mcp.utils import parse_erddap_json

COASTWATCH_URL = "https://coastwatch.pfeg.noaa.gov/erddap"


@pytest.fixture
async def client():
    c = ERDDAPClient()
    yield c
    await c.close()


@pytest.mark.asyncio
async def test_search_sst(client):
    """Search CoastWatch for 'sea surface temperature' — should return results."""
    data = await client.search(
        COASTWATCH_URL, "sea surface temperature", items_per_page=10
    )
    rows = parse_erddap_json(data)
    assert len(rows) > 0, "Expected search results for SST"
    # Check structure
    first = rows[0]
    assert "Dataset ID" in first or "datasetID" in first


@pytest.mark.asyncio
async def test_get_info_chlorophyll(client):
    """Get info for erdSW2018chlamday on CoastWatch — should return variables."""
    data = await client.get_info(COASTWATCH_URL, "erdSW2018chlamday")
    rows = parse_erddap_json(data)
    assert len(rows) > 0, "Expected info rows"
    # Should have dimension and variable rows
    row_types = {r.get("Row Type") for r in rows}
    assert (
        "variable" in row_types or "dimension" in row_types or "attribute" in row_types
    )


@pytest.mark.asyncio
async def test_get_tabledap_ndbc(client):
    """Get tabledap data from NDBC buoy dataset — should return rows."""
    # Get a small sample: single station, short time window, few variables
    query = "station,time,wtmp&station=%2246013%22&time>=2024-06-01T00:00:00Z&time<=2024-06-01T01:00:00Z"
    data = await client.get_tabledap(COASTWATCH_URL, "cwwcNDBCMet", query)
    rows = parse_erddap_json(data)
    assert len(rows) > 0, "Expected tabledap rows"


@pytest.mark.asyncio
async def test_get_all_datasets(client):
    """List all datasets on CoastWatch — should return 100+ datasets."""
    data = await client.get_all_datasets(COASTWATCH_URL, "datasetID,title")
    rows = parse_erddap_json(data)
    assert len(rows) > 100, f"Expected 100+ datasets, got {len(rows)}"


@pytest.mark.asyncio
async def test_get_griddap_small_subset(client):
    """Get a small griddap data subset — should return grid values."""
    # Single time step, small spatial area for erdSW2018chlamday
    query = "chlorophyll[(last)][(36):(37)][(-123):(-122)]"
    data = await client.get_griddap(COASTWATCH_URL, "erdSW2018chlamday", query)
    rows = parse_erddap_json(data)
    assert len(rows) > 0, "Expected griddap data rows"
    # Should have lat, lon, and chlorophyll columns
    first = rows[0]
    assert "latitude" in first or "chlorophyll" in first
