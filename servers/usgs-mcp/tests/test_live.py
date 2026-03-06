"""Integration tests for usgs-mcp against live USGS APIs."""

import pytest

from usgs_mcp.client import USGSClient


@pytest.fixture
async def client():
    """Create a USGSClient for live tests."""
    c = USGSClient()
    yield c
    await c.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_iv_potomac(client):
    """Fetch real instantaneous values from Potomac River at Little Falls."""
    data = await client.get_json(
        "iv",
        {
            "sites": "01646500",
            "parameterCd": "00060",
            "period": "PT2H",
        },
    )
    ts_list = data.get("value", {}).get("timeSeries", [])
    assert len(ts_list) > 0
    values = ts_list[0].get("values", [{}])[0].get("value", [])
    assert len(values) > 0
    assert float(values[-1]["value"]) > 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_site_info_potomac(client):
    """Fetch real site metadata for Potomac River at Little Falls."""
    rows = await client.get_rdb(
        "site",
        {
            "sites": "01646500",
            "siteOutput": "expanded",
        },
    )
    assert len(rows) > 0
    assert rows[0].get("site_no") == "01646500"
    assert "POTOMAC" in rows[0].get("station_nm", "").upper()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_dv_potomac(client):
    """Fetch real daily values from Potomac River."""
    data = await client.get_json(
        "dv",
        {
            "sites": "01646500",
            "parameterCd": "00060",
            "startDT": "2025-01-01",
            "endDT": "2025-01-07",
            "statCd": "00003",
        },
    )
    ts_list = data.get("value", {}).get("timeSeries", [])
    assert len(ts_list) > 0
    values = ts_list[0].get("values", [{}])[0].get("value", [])
    assert len(values) >= 5


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_peak_potomac(client):
    """Fetch real peak streamflow from Potomac River."""
    rows = await client.get_peak({"site_no": "01646500"})
    assert len(rows) > 10
    assert rows[0].get("site_no") == "01646500"
