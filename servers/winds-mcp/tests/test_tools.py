"""Unit tests for winds-mcp tool functions with mocked HTTP responses.

Tests cover station listing, station detail, nearest stations,
latest observation, observation time series, IEM history,
daily summary, and station comparison.

All HTTP calls are mocked using respx; no network access is required.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from winds_mcp.client import WindsClient
from winds_mcp.models import NWS_API_BASE

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    """Load a JSON fixture file by name."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


def _make_ctx(client: WindsClient) -> MagicMock:
    """Build a mock MCP Context whose lifespan_context holds the given WindsClient."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"winds_client": client}
    return ctx


# ---------------------------------------------------------------------------
# Shared pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def winds_client() -> WindsClient:
    """Create a bare WindsClient (its internal httpx client will be intercepted by respx)."""
    return WindsClient()


@pytest.fixture
def ctx(winds_client: WindsClient) -> MagicMock:
    """Create a mock Context wired to the WindsClient fixture."""
    return _make_ctx(winds_client)


# ===========================================================================
# Station tools
# ===========================================================================


class TestListStations:
    """Tests for the winds_list_stations tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_stations_ny(self, ctx: MagicMock) -> None:
        """List NY stations and verify markdown output contains station IDs."""
        from winds_mcp.tools.stations import winds_list_stations

        fixture = _load_fixture("nws_stations_ny.json")
        respx.get(f"{NWS_API_BASE}/stations").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await winds_list_stations(ctx, state="NY")

        assert "NWS Stations" in result
        assert "New York" in result
        assert "KJFK" in result
        assert "Kennedy" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_stations_json(self, ctx: MagicMock) -> None:
        """List stations with JSON response format."""
        from winds_mcp.tools.stations import winds_list_stations

        fixture = _load_fixture("nws_stations_ny.json")
        respx.get(f"{NWS_API_BASE}/stations").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await winds_list_stations(ctx, state="NY", response_format="json")

        parsed = json.loads(result)
        assert "features" in parsed
        assert len(parsed["features"]) == 3

    @pytest.mark.asyncio
    async def test_list_stations_invalid_state(self, ctx: MagicMock) -> None:
        """Verify validation error for invalid state code."""
        from winds_mcp.tools.stations import winds_list_stations

        result = await winds_list_stations(ctx, state="XX")

        assert "Validation Error" in result
        assert "XX" in result


class TestGetStation:
    """Tests for the winds_get_station tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_station_kjfk(self, ctx: MagicMock) -> None:
        """Get KJFK station metadata and verify output contains key fields."""
        from winds_mcp.tools.stations import winds_get_station

        fixture = _load_fixture("nws_station_kjfk.json")
        respx.get(f"{NWS_API_BASE}/stations/KJFK").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await winds_get_station(ctx, station_id="KJFK")

        assert "Station KJFK" in result
        assert "Kennedy" in result
        assert "40.63915" in result
        assert "-73.76393" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_station_not_found(self, ctx: MagicMock) -> None:
        """Verify error message for nonexistent station."""
        from winds_mcp.tools.stations import winds_get_station

        respx.get(f"{NWS_API_BASE}/stations/KXXX").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        result = await winds_get_station(ctx, station_id="KXXX")

        assert "Error" in result
        assert "not found" in result.lower()


class TestFindNearestStations:
    """Tests for the winds_find_nearest_stations tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_nearest_nyc(self, ctx: MagicMock) -> None:
        """Find stations near NYC and verify ordered results."""
        from winds_mcp.tools.stations import winds_find_nearest_stations

        fixture = _load_fixture("nws_nearest_stations.json")
        respx.get(url__regex=r".*/points/.*/stations").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await winds_find_nearest_stations(ctx, latitude=40.7, longitude=-74.0)

        assert "Nearest Stations" in result
        assert "KNYC" in result
        assert "Central Park" in result


# ===========================================================================
# Observation tools
# ===========================================================================


class TestGetLatestObservation:
    """Tests for the winds_get_latest_observation tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_latest_observation_markdown(self, ctx: MagicMock) -> None:
        """Fetch latest observation and verify markdown output."""
        from winds_mcp.tools.observations import winds_get_latest_observation

        fixture = _load_fixture("nws_latest_observation.json")
        respx.get(url__regex=r".*/observations/latest").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await winds_get_latest_observation(ctx, station_id="KJFK")

        assert "Latest Observation" in result
        assert "KJFK" in result
        assert "Wind Speed" in result
        assert "Wind Direction" in result
        assert "100" in result  # wind direction degrees
        assert "E" in result  # compass direction for 100 degrees

    @respx.mock
    @pytest.mark.asyncio
    async def test_latest_observation_english_units(self, ctx: MagicMock) -> None:
        """Fetch latest observation with english units."""
        from winds_mcp.models import Units
        from winds_mcp.tools.observations import winds_get_latest_observation

        fixture = _load_fixture("nws_latest_observation.json")
        respx.get(url__regex=r".*/observations/latest").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await winds_get_latest_observation(
            ctx, station_id="KJFK", units=Units.ENGLISH
        )

        assert "kt" in result
        assert "\u00b0F" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_latest_observation_json(self, ctx: MagicMock) -> None:
        """Fetch latest observation as JSON."""
        from winds_mcp.tools.observations import winds_get_latest_observation

        fixture = _load_fixture("nws_latest_observation.json")
        respx.get(url__regex=r".*/observations/latest").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await winds_get_latest_observation(
            ctx, station_id="KJFK", response_format="json"
        )

        parsed = json.loads(result)
        assert "properties" in parsed
        assert parsed["properties"]["stationId"] == "KJFK"


class TestGetObservations:
    """Tests for the winds_get_observations tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_observations_markdown(self, ctx: MagicMock) -> None:
        """Fetch observation time series and verify markdown table."""
        from winds_mcp.tools.observations import winds_get_observations

        fixture = _load_fixture("nws_observations.json")
        respx.get(url__regex=r".*/stations/.*/observations\b").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await winds_get_observations(ctx, station_id="KJFK", hours=24)

        assert "Observations" in result
        assert "KJFK" in result
        assert "Wind Spd" in result
        assert "3 observations" in result

    @pytest.mark.asyncio
    async def test_observations_invalid_hours(self, ctx: MagicMock) -> None:
        """Verify validation error for hours > 168."""
        from winds_mcp.tools.observations import winds_get_observations

        result = await winds_get_observations(ctx, station_id="KJFK", hours=200)

        assert "Validation Error" in result
        assert "168" in result


class TestGetHistory:
    """Tests for the winds_get_history tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_history_markdown(self, ctx: MagicMock) -> None:
        """Fetch IEM historical data and verify markdown table output."""
        from winds_mcp.tools.observations import winds_get_history

        # Mock the CSV response that the client will parse
        respx.get(url__regex=r".*/cgi-bin/request/asos.py").mock(
            return_value=httpx.Response(
                200,
                # Simulate CSV response that the client will parse
                text="station,valid,lon,lat,tmpf,dwpf,relh,drct,sknt,p01i,alti,mslp,vsby,gust\n"
                "JFK,2025-01-01 00:00,-73.7622,40.6386,49.00,42.00,76.67,90.00,14.00,M,29.72,1006.90,10.00,M\n"
                "JFK,2025-01-01 01:00,-73.7622,40.6386,50.00,44.00,79.00,90.00,17.00,0.00,29.65,1004.00,10.00,26.00\n",
            ),
        )

        result = await winds_get_history(
            ctx, station_id="KJFK", start_date="2025-01-01", end_date="2025-01-02"
        )

        assert "Historical ASOS" in result
        assert "2025-01-01" in result
        assert "2 observations" in result

    @pytest.mark.asyncio
    async def test_history_invalid_date_format(self, ctx: MagicMock) -> None:
        """Verify validation error for bad date format."""
        from winds_mcp.tools.observations import winds_get_history

        result = await winds_get_history(
            ctx, station_id="KJFK", start_date="01-01-2025", end_date="01-02-2025"
        )

        assert "Validation Error" in result

    @pytest.mark.asyncio
    async def test_history_date_range_too_large(self, ctx: MagicMock) -> None:
        """Verify validation error when date range exceeds 366 days."""
        from winds_mcp.tools.observations import winds_get_history

        result = await winds_get_history(
            ctx, station_id="KJFK", start_date="2023-01-01", end_date="2025-01-01"
        )

        assert "Validation Error" in result
        assert "366" in result


class TestGetDailySummary:
    """Tests for the winds_get_daily_summary tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_daily_summary_markdown(self, ctx: MagicMock) -> None:
        """Fetch daily summary and verify output has date rows."""
        from winds_mcp.tools.observations import winds_get_daily_summary

        respx.get(url__regex=r".*/cgi-bin/request/asos.py").mock(
            return_value=httpx.Response(
                200,
                text="station,valid,lon,lat,tmpf,dwpf,relh,drct,sknt,p01i,alti,mslp,vsby,gust\n"
                "JFK,2025-01-01 00:00,-73.7622,40.6386,49.00,42.00,76.67,90.00,14.00,M,29.72,1006.90,10.00,M\n"
                "JFK,2025-01-01 06:00,-73.7622,40.6386,50.00,44.00,79.00,90.00,17.00,0.00,29.65,1004.00,10.00,26.00\n"
                "JFK,2025-01-02 00:00,-73.7622,40.6386,42.00,28.00,58.45,310.00,18.00,0.00,29.90,1013.50,10.00,25.00\n",
            ),
        )

        result = await winds_get_daily_summary(
            ctx, station_id="KJFK", start_date="2025-01-01", end_date="2025-01-03"
        )

        assert "Daily Wind Summary" in result
        assert "2025-01-01" in result
        assert "2025-01-02" in result
        assert "2 days" in result


class TestCompareStations:
    """Tests for the winds_compare_stations tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_compare_two_stations(self, ctx: MagicMock) -> None:
        """Compare two stations and verify comparison table."""
        from winds_mcp.tools.observations import winds_compare_stations

        fixture = _load_fixture("nws_latest_observation.json")
        respx.get(url__regex=r".*/observations/latest").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await winds_compare_stations(ctx, station_ids=["KJFK", "KLGA"])

        assert "Station Comparison" in result
        assert "KJFK" in result
        assert "KLGA" in result
        assert "2 stations compared" in result

    @pytest.mark.asyncio
    async def test_compare_too_many_stations(self, ctx: MagicMock) -> None:
        """Verify validation error when exceeding 10 stations."""
        from winds_mcp.tools.observations import winds_compare_stations

        ids = [f"K{chr(65 + i)}{chr(65 + j)}K" for i in range(3) for j in range(4)]
        result = await winds_compare_stations(ctx, station_ids=ids)

        assert "Validation Error" in result
        assert "10" in result

    @pytest.mark.asyncio
    async def test_compare_too_few_stations(self, ctx: MagicMock) -> None:
        """Verify validation error when fewer than 2 stations."""
        from winds_mcp.tools.observations import winds_compare_stations

        result = await winds_compare_stations(ctx, station_ids=["KJFK"])

        assert "Validation Error" in result
        assert "2" in result


# ===========================================================================
# Error handling
# ===========================================================================


class TestErrorHandling:
    """Tests for error handling across tool functions."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_timeout_error(self, ctx: MagicMock) -> None:
        """Verify graceful handling of request timeouts."""
        from winds_mcp.tools.observations import winds_get_latest_observation

        respx.get(url__regex=r".*/observations/latest").mock(
            side_effect=httpx.ReadTimeout("timed out")
        )

        result = await winds_get_latest_observation(ctx, station_id="KJFK")

        assert "timed out" in result.lower() or "timeout" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_http_500_error(self, ctx: MagicMock) -> None:
        """Verify graceful handling of HTTP 500."""
        from winds_mcp.tools.stations import winds_list_stations

        respx.get(f"{NWS_API_BASE}/stations").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        result = await winds_list_stations(ctx, state="NY")

        assert "Error" in result
