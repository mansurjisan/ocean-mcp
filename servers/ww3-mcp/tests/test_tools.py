"""Unit tests for WW3 MCP tool functions with mocked HTTP.

Tests the tool functions in ww3_mcp.tools.discovery, ww3_mcp.tools.buoy,
and ww3_mcp.tools.forecast using respx to mock all outbound HTTP requests
and fixture files for realistic responses.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from ww3_mcp.client import WW3Client
from ww3_mcp.models import WAVE_GRIDS, WaveGrid

# ---------------------------------------------------------------------------
# Fixtures directory
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    """Load a fixture file and return its content as text."""
    return (FIXTURES_DIR / name).read_text()


def load_json_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Context helper
# ---------------------------------------------------------------------------


def make_ctx(client: WW3Client) -> MagicMock:
    """Create a mock MCP Context wired to the given WW3Client."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"ww3_client": client}
    return ctx


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    """Create a WW3Client and close it after the test."""
    c = WW3Client()
    yield c
    await c.close()


# ============================================================================
# Test: ww3_list_grids (pure data, no HTTP)
# ============================================================================


class TestWw3ListGrids:
    """Tests for the ww3_list_grids tool function."""

    async def test_list_grids_markdown_returns_all_grids(self, client):
        """ww3_list_grids in markdown mode should mention every grid ID."""
        from ww3_mcp.tools.discovery import ww3_list_grids

        ctx = make_ctx(client)
        result = await ww3_list_grids(ctx, response_format="markdown")

        assert "# GFS-Wave" in result
        for grid_id in WAVE_GRIDS:
            assert grid_id in result, f"Grid '{grid_id}' not found in output"

    async def test_list_grids_markdown_contains_table(self, client):
        """ww3_list_grids markdown output should include a table."""
        from ww3_mcp.tools.discovery import ww3_list_grids

        ctx = make_ctx(client)
        result = await ww3_list_grids(ctx, response_format="markdown")

        assert "| Grid ID |" in result
        assert "| --- |" in result

    async def test_list_grids_json_returns_valid_json(self, client):
        """ww3_list_grids JSON mode should return parseable JSON with all grids."""
        from ww3_mcp.tools.discovery import ww3_list_grids

        ctx = make_ctx(client)
        result = await ww3_list_grids(ctx, response_format="json")

        data = json.loads(result)
        assert isinstance(data, dict)
        assert len(data) == len(WAVE_GRIDS)

    async def test_list_grids_json_has_expected_keys(self, client):
        """Each grid in JSON output should have standard metadata keys."""
        from ww3_mcp.tools.discovery import ww3_list_grids

        ctx = make_ctx(client)
        result = await ww3_list_grids(ctx, response_format="json")

        data = json.loads(result)
        expected = {
            "name",
            "short_name",
            "resolution",
            "domain_desc",
            "domain",
            "cycles",
            "forecast_hours",
            "variables",
        }
        for grid_id, info in data.items():
            missing = expected - set(info.keys())
            assert not missing, f"Grid '{grid_id}' JSON missing keys: {missing}"

    async def test_list_grids_includes_variables_section(self, client):
        """ww3_list_grids markdown should include wave variables table."""
        from ww3_mcp.tools.discovery import ww3_list_grids

        ctx = make_ctx(client)
        result = await ww3_list_grids(ctx, response_format="markdown")

        assert "### Wave Variables" in result
        assert "HTSGW" in result


# ============================================================================
# Test: ww3_list_cycles (mocked S3 HEAD)
# ============================================================================


class TestWw3ListCycles:
    """Tests for the ww3_list_cycles tool, mocking AWS S3 HEAD requests."""

    @respx.mock
    async def test_list_cycles_all_available(self, client):
        """ww3_list_cycles should report 'Available' for cycles with 200 HEAD."""
        from ww3_mcp.tools.discovery import ww3_list_cycles

        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(200)
        )

        ctx = make_ctx(client)
        result = await ww3_list_cycles(
            ctx, grid=WaveGrid.GLOBAL_0P25, date="2026-03-01", num_days=1
        )

        assert "Available" in result
        assert "Not available" not in result

    @respx.mock
    async def test_list_cycles_none_available(self, client):
        """ww3_list_cycles should report 'Not available' when S3 returns 404."""
        from ww3_mcp.tools.discovery import ww3_list_cycles

        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(404)
        )

        ctx = make_ctx(client)
        result = await ww3_list_cycles(
            ctx, grid=WaveGrid.GLOBAL_0P25, date="2026-03-01", num_days=1
        )

        assert "Not available" in result
        assert "No cycles found" in result

    @respx.mock
    async def test_list_cycles_invalid_date_format(self, client):
        """ww3_list_cycles should return error for invalid date."""
        from ww3_mcp.tools.discovery import ww3_list_cycles

        ctx = make_ctx(client)
        result = await ww3_list_cycles(ctx, date="not-a-date")

        assert "Invalid date format" in result

    @respx.mock
    async def test_list_cycles_clamps_num_days(self, client):
        """ww3_list_cycles should clamp num_days to 1-7 range."""
        from ww3_mcp.tools.discovery import ww3_list_cycles

        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(200)
        )

        ctx = make_ctx(client)
        result = await ww3_list_cycles(ctx, date="2026-03-01", num_days=0)

        assert "1 day" in result

    @respx.mock
    async def test_list_cycles_connection_error_treated_as_unavailable(self, client):
        """ww3_list_cycles should treat connection errors as not available."""
        from ww3_mcp.tools.discovery import ww3_list_cycles

        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            side_effect=httpx.ConnectError("refused")
        )

        ctx = make_ctx(client)
        result = await ww3_list_cycles(ctx, date="2026-03-01", num_days=1)

        assert "Not available" in result


# ============================================================================
# Test: ww3_find_buoys (mocked NDBC stations XML)
# ============================================================================


class TestWw3FindBuoys:
    """Tests for the ww3_find_buoys tool with mocked NDBC XML."""

    @respx.mock
    async def test_find_buoys_returns_nearby_stations(self, client):
        """ww3_find_buoys should return stations within radius."""
        from ww3_mcp.tools.discovery import ww3_find_buoys

        xml = load_fixture("ndbc_stations.xml")
        respx.get("https://www.ndbc.noaa.gov/activestations.xml").mock(
            return_value=httpx.Response(200, text=xml)
        )

        ctx = make_ctx(client)
        # Near Diamond Shoals (41025 at 35.006, -75.402)
        result = await ww3_find_buoys(
            ctx, latitude=35.0, longitude=-75.5, radius_km=100
        )

        assert "41025" in result

    @respx.mock
    async def test_find_buoys_no_results(self, client):
        """ww3_find_buoys should report no buoys when none are within radius."""
        from ww3_mcp.tools.discovery import ww3_find_buoys

        xml = load_fixture("ndbc_stations.xml")
        respx.get("https://www.ndbc.noaa.gov/activestations.xml").mock(
            return_value=httpx.Response(200, text=xml)
        )

        ctx = make_ctx(client)
        # Middle of nowhere
        result = await ww3_find_buoys(ctx, latitude=0.0, longitude=0.0, radius_km=10)

        assert "No NDBC buoys found" in result

    @respx.mock
    async def test_find_buoys_json_format(self, client):
        """ww3_find_buoys JSON output should be valid JSON with station list."""
        from ww3_mcp.tools.discovery import ww3_find_buoys

        xml = load_fixture("ndbc_stations.xml")
        respx.get("https://www.ndbc.noaa.gov/activestations.xml").mock(
            return_value=httpx.Response(200, text=xml)
        )

        ctx = make_ctx(client)
        result = await ww3_find_buoys(
            ctx, latitude=35.0, longitude=-75.5, radius_km=100, response_format="json"
        )

        data = json.loads(result)
        assert "stations" in data
        assert data["count"] >= 1

    @respx.mock
    async def test_find_buoys_sorted_by_distance(self, client):
        """ww3_find_buoys results should be sorted by distance (nearest first)."""
        from ww3_mcp.tools.discovery import ww3_find_buoys

        xml = load_fixture("ndbc_stations.xml")
        respx.get("https://www.ndbc.noaa.gov/activestations.xml").mock(
            return_value=httpx.Response(200, text=xml)
        )

        ctx = make_ctx(client)
        result = await ww3_find_buoys(
            ctx, latitude=35.0, longitude=-75.5, radius_km=10000, response_format="json"
        )

        data = json.loads(result)
        distances = [s["distance_km"] for s in data["stations"]]
        assert distances == sorted(distances)


# ============================================================================
# Test: ww3_get_buoy_observations (mocked NDBC realtime)
# ============================================================================


class TestWw3GetBuoyObservations:
    """Tests for the ww3_get_buoy_observations tool with mocked NDBC data."""

    @respx.mock
    async def test_get_buoy_observations_returns_data(self, client):
        """ww3_get_buoy_observations should return wave data from NDBC."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_observations

        text = load_fixture("ndbc_realtime.txt")
        respx.get(url__startswith="https://www.ndbc.noaa.gov/data/realtime2/").mock(
            return_value=httpx.Response(200, text=text)
        )

        ctx = make_ctx(client)
        result = await ww3_get_buoy_observations(ctx, station_id="41025")

        assert "41025" in result
        assert "WVHT" in result

    @respx.mock
    async def test_get_buoy_observations_json(self, client):
        """ww3_get_buoy_observations JSON should return valid JSON."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_observations

        text = load_fixture("ndbc_realtime.txt")
        respx.get(url__startswith="https://www.ndbc.noaa.gov/data/realtime2/").mock(
            return_value=httpx.Response(200, text=text)
        )

        ctx = make_ctx(client)
        result = await ww3_get_buoy_observations(
            ctx, station_id="41025", response_format="json"
        )

        data = json.loads(result)
        assert data["station_id"] == "41025"
        assert data["records"] > 0

    @respx.mock
    async def test_get_buoy_observations_404(self, client):
        """ww3_get_buoy_observations should handle 404 errors gracefully."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_observations

        respx.get(url__startswith="https://www.ndbc.noaa.gov/data/realtime2/").mock(
            return_value=httpx.Response(404)
        )

        ctx = make_ctx(client)
        result = await ww3_get_buoy_observations(ctx, station_id="INVALID")

        assert "404" in result or "not found" in result.lower()

    @respx.mock
    async def test_get_buoy_observations_clamps_hours(self, client):
        """ww3_get_buoy_observations should clamp hours parameter."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_observations

        text = load_fixture("ndbc_realtime.txt")
        respx.get(url__startswith="https://www.ndbc.noaa.gov/data/realtime2/").mock(
            return_value=httpx.Response(200, text=text)
        )

        ctx = make_ctx(client)
        # hours=0 should be clamped to 1
        result = await ww3_get_buoy_observations(ctx, station_id="41025", hours=0)
        # Should not crash
        assert isinstance(result, str)


# ============================================================================
# Test: ww3_get_buoy_history (mocked NDBC history)
# ============================================================================


class TestWw3GetBuoyHistory:
    """Tests for the ww3_get_buoy_history tool with mocked NDBC data."""

    @respx.mock
    async def test_get_buoy_history_returns_data(self, client):
        """ww3_get_buoy_history should return historical wave data."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_history

        text = load_fixture("ndbc_realtime.txt")  # Reuse same format
        respx.get(url__startswith="https://www.ndbc.noaa.gov/view_text_file.php").mock(
            return_value=httpx.Response(200, text=text)
        )

        ctx = make_ctx(client)
        result = await ww3_get_buoy_history(ctx, station_id="41025", year=2023)

        assert "Historical Data" in result

    @respx.mock
    async def test_get_buoy_history_404(self, client):
        """ww3_get_buoy_history should handle missing year gracefully."""
        from ww3_mcp.tools.buoy import ww3_get_buoy_history

        respx.get(url__startswith="https://www.ndbc.noaa.gov/view_text_file.php").mock(
            return_value=httpx.Response(404)
        )

        ctx = make_ctx(client)
        result = await ww3_get_buoy_history(ctx, station_id="41025", year=1900)

        assert "404" in result or "not found" in result.lower()


# ============================================================================
# Test: client methods
# ============================================================================


class TestWW3Client:
    """Tests for WW3Client utility methods."""

    def test_build_grib_filter_url_basic(self):
        """build_grib_filter_url should produce correct NOMADS URL."""
        c = WW3Client()
        url = c.build_grib_filter_url("global.0p25", "20260301", "00", 6)

        assert "nomads.ncep.noaa.gov" in url
        assert "gfswave.t00z.global.0p25.f006.grib2" in url

    def test_build_grib_filter_url_with_variables(self):
        """build_grib_filter_url should include variable filter parameters."""
        c = WW3Client()
        url = c.build_grib_filter_url(
            "global.0p25", "20260301", "00", 0, variables=["HTSGW", "PERPW"]
        )

        assert "var_HTSGW=on" in url
        assert "var_PERPW=on" in url

    def test_build_grib_filter_url_with_subsetting(self):
        """build_grib_filter_url should include lat/lon subsetting."""
        c = WW3Client()
        url = c.build_grib_filter_url(
            "global.0p25",
            "20260301",
            "00",
            0,
            lat_range=(34.0, 36.0),
            lon_range=(284.0, 286.0),
        )

        assert "toplat=36.0" in url
        assert "bottomlat=34.0" in url
        assert "leftlon=284.0" in url
        assert "rightlon=286.0" in url

    def test_build_s3_grib_url(self):
        """build_s3_grib_url should produce correct S3 URL."""
        c = WW3Client()
        url = c.build_s3_grib_url("global.0p25", "20260301", "00", 0)

        assert "noaa-gfs-bdp-pds.s3.amazonaws.com" in url
        assert "gfswave.t00z.global.0p25.f000.grib2" in url

    @respx.mock
    async def test_check_grib_exists_true(self, client):
        """check_grib_exists should return True for 200 HEAD."""
        url = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/test.grib2"
        respx.head(url).mock(return_value=httpx.Response(200))

        assert await client.check_grib_exists(url) is True

    @respx.mock
    async def test_check_grib_exists_false(self, client):
        """check_grib_exists should return False for 404 HEAD."""
        url = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/missing.grib2"
        respx.head(url).mock(return_value=httpx.Response(404))

        assert await client.check_grib_exists(url) is False

    @respx.mock
    async def test_check_grib_exists_connection_error(self, client):
        """check_grib_exists should return False on connection error."""
        url = "https://noaa-gfs-bdp-pds.s3.amazonaws.com/error.grib2"
        respx.head(url).mock(side_effect=httpx.ConnectError("refused"))

        assert await client.check_grib_exists(url) is False


# ============================================================================
# Test: resolve_latest_cycle (mocked S3 HEAD)
# ============================================================================


class TestResolveLatestCycle:
    """Tests for WW3Client.resolve_latest_cycle with mocked HEAD."""

    @respx.mock
    async def test_resolve_returns_none_when_nothing_available(self, client):
        """resolve_latest_cycle should return None if all checks fail."""
        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(404)
        )

        result = await client.resolve_latest_cycle("global.0p25", num_days=1)
        assert result is None

    @respx.mock
    async def test_resolve_finds_available_cycle(self, client):
        """resolve_latest_cycle should return the first available cycle."""
        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(200)
        )

        result = await client.resolve_latest_cycle("global.0p25", num_days=1)
        assert result is not None
        date_str, cycle_str = result
        assert len(date_str) == 8
        assert cycle_str in {"00", "06", "12", "18"}


# ============================================================================
# Test: error handling
# ============================================================================


class TestHandleWw3Error:
    """Tests for the handle_ww3_error utility."""

    def test_handle_http_404(self):
        """handle_ww3_error should return a descriptive message for 404."""
        from ww3_mcp.utils import handle_ww3_error

        response = httpx.Response(
            404, request=httpx.Request("GET", "https://example.com")
        )
        err = httpx.HTTPStatusError(
            "Not Found", request=response.request, response=response
        )
        msg = handle_ww3_error(err, "global.0p25")
        assert "404" in msg

    def test_handle_timeout(self):
        """handle_ww3_error should return a timeout message."""
        from ww3_mcp.utils import handle_ww3_error

        err = httpx.TimeoutException("timed out")
        msg = handle_ww3_error(err)
        assert "timed out" in msg.lower()

    def test_handle_value_error(self):
        """handle_ww3_error should pass through ValueError messages."""
        from ww3_mcp.utils import handle_ww3_error

        err = ValueError("bad input")
        msg = handle_ww3_error(err)
        assert msg == "bad input"

    def test_handle_generic_error(self):
        """handle_ww3_error should format unexpected errors."""
        from ww3_mcp.utils import handle_ww3_error

        err = TypeError("unexpected")
        msg = handle_ww3_error(err, "test")
        assert "TypeError" in msg
        assert "test" in msg


# ============================================================================
# Test: forecast tools with mocked extract_grib_point
# ============================================================================


class TestWw3GetPointSnapshot:
    """Tests for ww3_get_point_snapshot with mocked GRIB extraction."""

    @respx.mock
    async def test_snapshot_no_cycles_returns_error(self, client):
        """ww3_get_point_snapshot should return error when no cycles found."""
        from ww3_mcp.tools.forecast import ww3_get_point_snapshot

        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(404)
        )

        ctx = make_ctx(client)
        result = await ww3_get_point_snapshot(ctx, latitude=35.0, longitude=-75.0)

        assert "No GFS-Wave cycles found" in result

    @respx.mock
    async def test_snapshot_with_mocked_grib(self, client):
        """ww3_get_point_snapshot with mocked download and extraction."""
        from ww3_mcp.tools.forecast import ww3_get_point_snapshot

        grib_data = load_json_fixture("grib_sample.json")

        # Mock S3 HEAD for cycle resolution
        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(200)
        )

        # Mock NOMADS GRIB download
        respx.get(url__startswith="https://nomads.ncep.noaa.gov/").mock(
            return_value=httpx.Response(200, content=b"fake grib data")
        )

        ctx = make_ctx(client)

        with patch("ww3_mcp.tools.forecast.extract_grib_point", return_value=grib_data):
            result = await ww3_get_point_snapshot(
                ctx, latitude=35.0, longitude=-75.0, response_format="json"
            )

        data = json.loads(result)
        assert "variables" in data
        assert data["variables"]["HTSGW"] == 1.85


class TestWw3GetForecastAtPoint:
    """Tests for ww3_get_forecast_at_point with mocked GRIB extraction."""

    @respx.mock
    async def test_forecast_no_cycles_returns_error(self, client):
        """ww3_get_forecast_at_point should return error when no cycles found."""
        from ww3_mcp.tools.forecast import ww3_get_forecast_at_point

        respx.head(url__startswith="https://noaa-gfs-bdp-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(404)
        )

        ctx = make_ctx(client)
        result = await ww3_get_forecast_at_point(ctx, latitude=35.0, longitude=-75.0)

        assert "No GFS-Wave cycles found" in result
