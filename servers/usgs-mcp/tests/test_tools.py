"""Unit tests for usgs-mcp tools with mocked HTTP responses."""

import json
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from usgs_mcp.client import USGSClient
from usgs_mcp.models import USGS_BASE_URL, USGS_PEAK_URL
from usgs_mcp.tools.flood import usgs_get_flood_status, usgs_get_peak_streamflow
from usgs_mcp.tools.sites import (
    usgs_find_nearest_sites,
    usgs_find_sites,
    usgs_get_site_info,
)
from usgs_mcp.tools.statistics import usgs_get_daily_stats, usgs_get_monthly_stats
from usgs_mcp.tools.streamflow import (
    usgs_get_daily_values,
    usgs_get_hydrograph,
    usgs_get_instantaneous_values,
)

from .conftest import load_fixture, load_json_fixture


@pytest.fixture
def usgs_client():
    """Create a fresh USGSClient for each test."""
    return USGSClient()


@pytest.fixture
def ctx(usgs_client):
    """Create a mock MCP Context."""
    mock_ctx = MagicMock()
    mock_ctx.request_context.lifespan_context = {"usgs_client": usgs_client}
    return mock_ctx


# --- Site Tools ---


class TestFindSites:
    """Tests for usgs_find_sites tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_sites_by_state(self, ctx):
        """Find sites in Maryland returns tabular output."""
        rdb_text = load_fixture("site_search.rdb")
        respx.get(f"{USGS_BASE_URL}/site/").mock(
            return_value=httpx.Response(200, text=rdb_text)
        )
        result = await usgs_find_sites(ctx, state_code="MD")
        assert "USGS Sites" in result
        assert "01646500" in result or "Site ID" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_sites_json_format(self, ctx):
        """Find sites in JSON format returns valid JSON."""
        rdb_text = load_fixture("site_search.rdb")
        respx.get(f"{USGS_BASE_URL}/site/").mock(
            return_value=httpx.Response(200, text=rdb_text)
        )
        result = await usgs_find_sites(ctx, state_code="MD", response_format="json")
        parsed = json.loads(result)
        assert isinstance(parsed, list)

    @pytest.mark.asyncio
    async def test_find_sites_no_criteria(self, ctx):
        """Find sites with no state or bbox returns validation error."""
        result = await usgs_find_sites(ctx)
        assert "Validation Error" in result

    @pytest.mark.asyncio
    async def test_find_sites_invalid_state(self, ctx):
        """Find sites with invalid state code returns validation error."""
        result = await usgs_find_sites(ctx, state_code="ZZ")
        assert "Validation Error" in result


class TestGetSiteInfo:
    """Tests for usgs_get_site_info tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_site_info_markdown(self, ctx):
        """Get site info returns metadata in markdown."""
        rdb_text = load_fixture("site_info.rdb")
        respx.get(f"{USGS_BASE_URL}/site/").mock(
            return_value=httpx.Response(200, text=rdb_text)
        )
        result = await usgs_get_site_info(ctx, site_number="01646500")
        assert "USGS Site" in result
        assert "Latitude" in result or "Name" in result

    @pytest.mark.asyncio
    async def test_get_site_info_invalid_number(self, ctx):
        """Get site info with short site number returns validation error."""
        result = await usgs_get_site_info(ctx, site_number="123")
        assert "Validation Error" in result


class TestFindNearestSites:
    """Tests for usgs_find_nearest_sites tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_nearest_sites(self, ctx):
        """Find nearest sites returns sorted results."""
        rdb_text = load_fixture("site_search.rdb")
        respx.get(f"{USGS_BASE_URL}/site/").mock(
            return_value=httpx.Response(200, text=rdb_text)
        )
        result = await usgs_find_nearest_sites(ctx, latitude=38.9, longitude=-77.1)
        assert "Nearest USGS Sites" in result

    @pytest.mark.asyncio
    async def test_find_nearest_sites_invalid_lat(self, ctx):
        """Find nearest sites with out-of-range latitude returns validation error."""
        result = await usgs_find_nearest_sites(ctx, latitude=200.0, longitude=-77.0)
        assert "Validation Error" in result


# --- Streamflow Tools ---


class TestGetInstantaneousValues:
    """Tests for usgs_get_instantaneous_values tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_iv_markdown(self, ctx):
        """Get instantaneous values returns formatted output."""
        iv_json = load_json_fixture("iv_response.json")
        respx.get(f"{USGS_BASE_URL}/iv/").mock(
            return_value=httpx.Response(200, json=iv_json)
        )
        result = await usgs_get_instantaneous_values(ctx, site_number="01646500")
        assert "Instantaneous Values" in result
        assert "Current" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_iv_json_format(self, ctx):
        """Get instantaneous values in JSON format."""
        iv_json = load_json_fixture("iv_response.json")
        respx.get(f"{USGS_BASE_URL}/iv/").mock(
            return_value=httpx.Response(200, json=iv_json)
        )
        result = await usgs_get_instantaneous_values(
            ctx, site_number="01646500", response_format="json"
        )
        parsed = json.loads(result)
        assert "value" in parsed

    @pytest.mark.asyncio
    async def test_get_iv_invalid_site(self, ctx):
        """Get IV with invalid site number returns validation error."""
        result = await usgs_get_instantaneous_values(ctx, site_number="abc")
        assert "Validation Error" in result


class TestGetDailyValues:
    """Tests for usgs_get_daily_values tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_dv_markdown(self, ctx):
        """Get daily values returns formatted table."""
        dv_json = load_json_fixture("dv_response.json")
        respx.get(f"{USGS_BASE_URL}/dv/").mock(
            return_value=httpx.Response(200, json=dv_json)
        )
        result = await usgs_get_daily_values(
            ctx, site_number="01646500", start_date="2025-01-01", end_date="2025-01-07"
        )
        assert "Daily Values" in result
        assert "2025-01" in result

    @pytest.mark.asyncio
    async def test_get_dv_bad_date_format(self, ctx):
        """Get daily values with bad date format returns validation error."""
        result = await usgs_get_daily_values(
            ctx, site_number="01646500", start_date="01-01-2025", end_date="01-07-2025"
        )
        assert "Validation Error" in result

    @pytest.mark.asyncio
    async def test_get_dv_end_before_start(self, ctx):
        """Get daily values with end before start returns validation error."""
        result = await usgs_get_daily_values(
            ctx, site_number="01646500", start_date="2025-01-07", end_date="2025-01-01"
        )
        assert "Validation Error" in result


class TestGetHydrograph:
    """Tests for usgs_get_hydrograph tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_hydrograph(self, ctx):
        """Get hydrograph returns summary with trend."""
        iv_json = load_json_fixture("iv_response.json")
        stat_rdb = load_fixture("daily_stats.rdb")
        respx.get(f"{USGS_BASE_URL}/iv/").mock(
            return_value=httpx.Response(200, json=iv_json)
        )
        respx.get(f"{USGS_BASE_URL}/stat/").mock(
            return_value=httpx.Response(200, text=stat_rdb)
        )
        result = await usgs_get_hydrograph(ctx, site_number="01646500")
        assert "Hydrograph Summary" in result
        assert "Current" in result
        assert "Trend" in result

    @pytest.mark.asyncio
    async def test_get_hydrograph_invalid_days(self, ctx):
        """Get hydrograph with days > 120 returns validation error."""
        result = await usgs_get_hydrograph(ctx, site_number="01646500", days=200)
        assert "Validation Error" in result


# --- Flood Tools ---


class TestGetPeakStreamflow:
    """Tests for usgs_get_peak_streamflow tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_peak_markdown(self, ctx):
        """Get peak streamflow returns table with MAX marker."""
        rdb_text = load_fixture("peak_streamflow.rdb")
        respx.get(USGS_PEAK_URL).mock(return_value=httpx.Response(200, text=rdb_text))
        result = await usgs_get_peak_streamflow(ctx, site_number="01646500")
        assert "Peak Streamflow" in result
        assert "MAX" in result

    @pytest.mark.asyncio
    async def test_get_peak_invalid_site(self, ctx):
        """Get peak with invalid site returns validation error."""
        result = await usgs_get_peak_streamflow(ctx, site_number="short")
        assert "Validation Error" in result


class TestGetFloodStatus:
    """Tests for usgs_get_flood_status tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_flood_status(self, ctx):
        """Get flood status returns current status assessment."""
        iv_json = load_json_fixture("iv_response.json")
        peak_rdb = load_fixture("peak_streamflow.rdb")
        stat_rdb = load_fixture("daily_stats.rdb")
        respx.get(f"{USGS_BASE_URL}/iv/").mock(
            return_value=httpx.Response(200, json=iv_json)
        )
        respx.get(USGS_PEAK_URL).mock(return_value=httpx.Response(200, text=peak_rdb))
        respx.get(f"{USGS_BASE_URL}/stat/").mock(
            return_value=httpx.Response(200, text=stat_rdb)
        )
        result = await usgs_get_flood_status(ctx, site_number="01646500")
        assert "Flood Status" in result
        assert "Current Flow" in result

    @pytest.mark.asyncio
    async def test_get_flood_status_invalid_site(self, ctx):
        """Get flood status with invalid site returns validation error."""
        result = await usgs_get_flood_status(ctx, site_number="bad")
        assert "Validation Error" in result


# --- Statistics Tools ---


class TestGetMonthlyStats:
    """Tests for usgs_get_monthly_stats tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_monthly_stats(self, ctx):
        """Get monthly stats returns table by month."""
        rdb_text = load_fixture("monthly_stats.rdb")
        respx.get(f"{USGS_BASE_URL}/stat/").mock(
            return_value=httpx.Response(200, text=rdb_text)
        )
        result = await usgs_get_monthly_stats(ctx, site_number="01646500")
        assert "Monthly Statistics" in result

    @pytest.mark.asyncio
    async def test_get_monthly_stats_invalid_site(self, ctx):
        """Get monthly stats with invalid site returns validation error."""
        result = await usgs_get_monthly_stats(ctx, site_number="12")
        assert "Validation Error" in result


class TestGetDailyStats:
    """Tests for usgs_get_daily_stats tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_daily_stats(self, ctx):
        """Get daily stats returns percentile table."""
        rdb_text = load_fixture("daily_stats.rdb")
        respx.get(f"{USGS_BASE_URL}/stat/").mock(
            return_value=httpx.Response(200, text=rdb_text)
        )
        result = await usgs_get_daily_stats(ctx, site_number="01646500")
        assert "Daily Statistics" in result

    @pytest.mark.asyncio
    async def test_get_daily_stats_invalid_month(self, ctx):
        """Get daily stats with invalid month returns validation error."""
        result = await usgs_get_daily_stats(ctx, site_number="01646500", month=13)
        assert "Validation Error" in result


# --- Error Handling ---


class TestErrorHandling:
    """Tests for error handling across tools."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_timeout_error(self, ctx):
        """Timeout errors return user-friendly message."""
        respx.get(f"{USGS_BASE_URL}/iv/").mock(side_effect=httpx.ReadTimeout("timeout"))
        result = await usgs_get_instantaneous_values(ctx, site_number="01646500")
        assert "timed out" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_http_500_error(self, ctx):
        """HTTP 500 errors return user-friendly message."""
        respx.get(f"{USGS_BASE_URL}/iv/").mock(return_value=httpx.Response(500))
        result = await usgs_get_instantaneous_values(ctx, site_number="01646500")
        assert "Error" in result
