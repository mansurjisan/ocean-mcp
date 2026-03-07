"""Live integration tests for ndbc-mcp — hit real NDBC APIs.

Run with: pytest tests/test_live.py -v
"""

import pytest


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_list_stations():
    """Fetch live active station list from NDBC."""
    from ndbc_mcp.client import NDBCClient

    client = NDBCClient()
    try:
        stations = await client.get_active_stations()
        assert len(stations) > 100, f"Expected >100 stations, got {len(stations)}"
        # Verify station structure
        s = stations[0]
        assert "id" in s
        assert "lat" in s
        assert "lon" in s
    finally:
        await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_station_metadata():
    """Fetch metadata for a well-known station (44013 - Boston)."""
    from ndbc_mcp.client import NDBCClient

    client = NDBCClient()
    try:
        station = await client.get_station_metadata("44013")
        assert station is not None
        assert station["id"] == "44013"
        assert station["type"] == "buoy"
    finally:
        await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_observations_44013():
    """Fetch recent observations from station 44013 (Boston buoy)."""
    from ndbc_mcp.client import NDBCClient

    client = NDBCClient()
    try:
        columns, records = await client.get_observations("44013", hours=6)
        assert len(columns) > 5, "Expected multiple columns"
        # There should be recent data (updated every 10 min)
        assert len(records) >= 1, "Expected at least 1 recent observation"
        assert records[0].get("datetime") is not None
    finally:
        await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_spectral_data():
    """Fetch spectral wave data from station 44013."""
    from ndbc_mcp.client import NDBCClient

    client = NDBCClient()
    try:
        columns, records = await client.get_observations(
            "44013", hours=6, extension="spec"
        )
        assert len(columns) > 5, "Expected spectral columns"
        if records:
            # Spectral files should have SwH (swell height)
            assert "SwH" in columns or "WVHT" in columns
    finally:
        await client.close()
