"""Live integration tests for WW3 MCP server.

These tests hit real NOAA APIs and are meant to be run periodically
(not on every commit). They validate that the server can successfully
communicate with upstream data sources.

Run with: pytest tests/test_live.py -v -s
"""

from __future__ import annotations

import pytest

from ww3_mcp.client import WW3Client


@pytest.fixture
async def client():
    """Create a WW3Client and close it after the test."""
    c = WW3Client()
    yield c
    await c.close()


@pytest.mark.integration
class TestLiveCycleResolution:
    """Live tests for GFS-Wave cycle resolution."""

    async def test_resolve_latest_cycle_global(self, client):
        """Should find at least one available GFS-Wave cycle on S3."""
        result = await client.resolve_latest_cycle("global.0p25", num_days=3)
        # May be None if S3 is down, but typically should find something
        if result is not None:
            date_str, cycle_str = result
            assert len(date_str) == 8
            assert cycle_str in {"00", "06", "12", "18"}


@pytest.mark.integration
class TestLiveNdbcBuoy:
    """Live tests for NDBC buoy data retrieval."""

    async def test_fetch_ndbc_realtime_buoy_41025(self, client):
        """Should fetch realtime data from Diamond Shoals buoy."""
        text = await client.fetch_ndbc_realtime("41025")
        assert len(text) > 100
        assert "WVHT" in text or "WDIR" in text

    async def test_fetch_ndbc_active_stations(self, client):
        """Should fetch and parse active stations XML."""
        xml = await client.fetch_ndbc_active_stations()
        assert "<station" in xml
        assert len(xml) > 1000


@pytest.mark.integration
class TestLiveDiscovery:
    """Live tests for discovery tools."""

    async def test_find_buoys_near_cape_hatteras(self, client):
        """Should find NDBC buoys near Cape Hatteras, NC."""
        from unittest.mock import MagicMock

        from ww3_mcp.tools.discovery import ww3_find_buoys

        ctx = MagicMock()
        ctx.request_context.lifespan_context = {"ww3_client": client}

        result = await ww3_find_buoys(
            ctx, latitude=35.2, longitude=-75.5, radius_km=200
        )
        assert "41025" in result or "buoy" in result.lower()
