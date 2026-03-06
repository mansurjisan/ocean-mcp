"""Unit tests for RTOFS tools with mocked HTTP (respx)."""

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from rtofs_mcp.client import RTOFSClient
from rtofs_mcp.models import DATASETS, THREDDS_BASE

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _mock_ctx(client: RTOFSClient):
    """Create a mock MCP Context with an RTOFSClient in lifespan."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"rtofs_client": client}
    return ctx


class TestFetchPointCSV:
    """Test client.fetch_point_csv with mocked HTTP."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_ssh_point(self):
        """Fetch SSH at a point returns parsed CSV data."""
        fixture_text = FIXTURES_DIR.joinpath("ssh_point.csv").read_text()
        ds = DATASETS["ssh"]
        url = f"{THREDDS_BASE}/ncss/{ds['path']}"

        respx.get(url).mock(return_value=httpx.Response(200, text=fixture_text))

        client = RTOFSClient()
        try:
            rows = await client.fetch_point_csv(
                dataset_key="ssh",
                variable="surf_el",
                latitude=40.0,
                longitude=-74.0,
                time="present",
            )
            assert len(rows) >= 1
            assert "surf_el" in rows[0]
            assert "latitude" in rows[0]
            assert "time" in rows[0]
            assert isinstance(rows[0]["surf_el"], float)
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_temp_profile(self):
        """Fetch temperature profile returns rows with depth."""
        fixture_text = FIXTURES_DIR.joinpath("temp_profile.csv").read_text()
        ds = DATASETS["sst"]
        url = f"{THREDDS_BASE}/ncss/{ds['path']}"

        respx.get(url).mock(return_value=httpx.Response(200, text=fixture_text))

        client = RTOFSClient()
        try:
            rows = await client.fetch_point_csv(
                dataset_key="sst",
                variable="water_temp",
                latitude=40.0,
                longitude=-74.0,
                time="present",
            )
            assert len(rows) >= 1
            assert "water_temp" in rows[0]
            assert "vertCoord" in rows[0]
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_sst_timeseries(self):
        """Fetch SST surface time series returns multiple rows."""
        fixture_text = FIXTURES_DIR.joinpath("sst_timeseries.csv").read_text()
        ds = DATASETS["sst"]
        url = f"{THREDDS_BASE}/ncss/{ds['path']}"

        respx.get(url).mock(return_value=httpx.Response(200, text=fixture_text))

        client = RTOFSClient()
        try:
            rows = await client.fetch_point_csv(
                dataset_key="sst",
                variable="water_temp",
                latitude=40.0,
                longitude=-74.0,
                vert_coord=0.0,
            )
            assert len(rows) > 10
            # All should have the same lat/lon
            lats = {r["latitude"] for r in rows}
            assert len(lats) == 1
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_handles_404(self):
        """HTTP 404 should raise RTOFSAPIError."""
        from rtofs_mcp.client import RTOFSAPIError

        ds = DATASETS["ssh"]
        url = f"{THREDDS_BASE}/ncss/{ds['path']}"
        respx.get(url).mock(return_value=httpx.Response(404, text="Not Found"))

        client = RTOFSClient()
        try:
            with pytest.raises(RTOFSAPIError, match="404"):
                await client.fetch_point_csv(
                    dataset_key="ssh",
                    variable="surf_el",
                    latitude=40.0,
                    longitude=-74.0,
                )
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_handles_timeout(self):
        """Timeout should raise RTOFSAPIError."""
        from rtofs_mcp.client import RTOFSAPIError

        ds = DATASETS["ssh"]
        url = f"{THREDDS_BASE}/ncss/{ds['path']}"
        respx.get(url).mock(side_effect=httpx.ReadTimeout("timeout"))

        client = RTOFSClient()
        try:
            with pytest.raises(RTOFSAPIError, match="timed out"):
                await client.fetch_point_csv(
                    dataset_key="ssh",
                    variable="surf_el",
                    latitude=40.0,
                    longitude=-74.0,
                )
        finally:
            await client.close()


class TestCheckDatasetAvailable:
    """Test dataset availability checking."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_available_dataset(self):
        """Available dataset returns True."""
        ds = DATASETS["ssh"]
        url = f"{THREDDS_BASE}/dodsC/{ds['path']}.dds"
        respx.get(url).mock(return_value=httpx.Response(200, text="Dataset {}"))

        client = RTOFSClient()
        try:
            result = await client.check_dataset_available("ssh")
            assert result is True
        finally:
            await client.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_unavailable_dataset(self):
        """404 response returns False."""
        ds = DATASETS["ssh"]
        url = f"{THREDDS_BASE}/dodsC/{ds['path']}.dds"
        respx.get(url).mock(return_value=httpx.Response(404))

        client = RTOFSClient()
        try:
            result = await client.check_dataset_available("ssh")
            assert result is False
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_unknown_dataset_key(self):
        """Unknown dataset key returns False without network call."""
        client = RTOFSClient()
        try:
            result = await client.check_dataset_available("nonexistent")
            assert result is False
        finally:
            await client.close()


class TestToolRegistration:
    """Verify all 8 tools are registered on the MCP server."""

    def test_all_tools_registered(self):
        """All 8 RTOFS tools should be registered."""
        from rtofs_mcp.server import mcp

        tool_names = {t.name for t in mcp._tool_manager.list_tools()}
        expected = {
            "rtofs_get_system_info",
            "rtofs_list_datasets",
            "rtofs_get_latest_time",
            "rtofs_get_surface_forecast",
            "rtofs_get_profile_forecast",
            "rtofs_get_area_forecast",
            "rtofs_get_transect",
            "rtofs_compare_with_observations",
        }
        for name in expected:
            assert name in tool_names, f"Tool '{name}' not registered"
