"""Unit tests for winds-mcp tool functions with mocked HTTP responses.

Tests cover station listing, station detail, nearest stations,
latest observation, observation time series, IEM history,
daily summary, and station comparison.

All HTTP calls are mocked using respx; no network access is required.
"""

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from winds_mcp.client import (
    RetryTransport,
    WindsAPIError,
    WindsClient,
    handle_winds_error,
)
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
    """Create a bare WindsClient (intercepted by respx; backoff_factor=0 so
    retries replay instantly)."""
    return WindsClient(backoff_factor=0)


@pytest.fixture
def ctx(winds_client: WindsClient) -> MagicMock:
    """Create a mock Context wired to the WindsClient fixture."""
    return _make_ctx(winds_client)


@pytest.mark.asyncio
async def test_client_uses_retry_transport() -> None:
    """The shared httpx client is mounted on the RetryTransport."""
    c = WindsClient()
    client = await c._get_client()
    try:
        assert isinstance(client._transport, RetryTransport)
    finally:
        await c.close()


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
        assert "features" in parsed["data"]
        assert len(parsed["data"]["features"]) == 3
        assert parsed["truncated"] is False
        assert parsed["returned"] == 3
        assert parsed["total"] == 3

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
        assert "properties" in parsed["data"]
        assert parsed["data"]["properties"]["stationId"] == "KJFK"


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

    def test_windsapi_error_is_recognized_not_dead_branch(self) -> None:
        """handle_winds_error must check isinstance(e, WindsAPIError) — the
        original code tested `isinstance(e, WindsClient)` (the client
        *class*, never an exception instance) which was always False and
        so never fired. WindsAPIError is a real exception type and must be
        recognized."""
        result = handle_winds_error(WindsAPIError("something bad happened"))
        assert result == "Winds Error: something bad happened"
        # A WindsClient instance is not an exception and could never be the
        # `e` passed to handle_winds_error in the first place — confirming
        # the fix targets the exception type, not the client class.
        assert not isinstance(WindsClient(), Exception)

    @respx.mock
    @pytest.mark.asyncio
    async def test_malformed_nws_json_raises_windsapierror(
        self, ctx: MagicMock
    ) -> None:
        """A 200 response with a non-JSON body (e.g. a gateway error page)
        is the server's own semantic error — surfaced as WindsAPIError via
        handle_winds_error, not a raw json.JSONDecodeError repr."""
        from winds_mcp.tools.stations import winds_get_station

        respx.get(f"{NWS_API_BASE}/stations/KJFK").mock(
            return_value=httpx.Response(200, text="<html>Bad Gateway</html>")
        )

        result = await winds_get_station(ctx, station_id="KJFK")

        assert result.startswith("Winds Error:")

    @respx.mock
    @pytest.mark.asyncio
    async def test_malformed_iem_csv_raises_windsapierror(self, ctx: MagicMock) -> None:
        """A degraded IEM response that doesn't look like ASOS CSV (missing
        the expected 'station' column) is flagged as WindsAPIError instead
        of silently parsing into garbage rows."""
        from winds_mcp.tools.observations import winds_get_history

        respx.get(url__regex=r".*/cgi-bin/request/asos.py").mock(
            return_value=httpx.Response(200, text="<html>Service Unavailable</html>")
        )

        result = await winds_get_history(
            ctx, station_id="KJFK", start_date="2025-01-01", end_date="2025-01-02"
        )

        assert result.startswith("Winds Error:")


# ===========================================================================
# JSON output discipline: retrieved_at, truncation envelope, cap direction
# ===========================================================================


class TestJsonEnvelope:
    """Tests for the retrieved_at + truncation envelope every JSON response
    now carries (CONVENTIONS.md "JSON response wrappers" / "Output caps")."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_retrieved_at_present_and_iso8601(self, ctx: MagicMock) -> None:
        """Every JSON response carries a parseable ISO 8601 retrieved_at."""
        from winds_mcp.tools.stations import winds_get_station

        fixture = _load_fixture("nws_station_kjfk.json")
        respx.get(f"{NWS_API_BASE}/stations/KJFK").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await winds_get_station(ctx, station_id="KJFK", response_format="json")
        parsed = json.loads(result)

        assert "retrieved_at" in parsed
        # Must round-trip through datetime.fromisoformat without error.
        datetime.fromisoformat(parsed["retrieved_at"])

    @respx.mock
    @pytest.mark.asyncio
    async def test_single_object_response_not_truncated(self, ctx: MagicMock) -> None:
        """A single-object JSON payload (no list to cap) always reports
        truncated=False, returned=1, total=1."""
        from winds_mcp.tools.observations import winds_get_latest_observation

        fixture = _load_fixture("nws_latest_observation.json")
        respx.get(url__regex=r".*/observations/latest").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await winds_get_latest_observation(
            ctx, station_id="KJFK", response_format="json"
        )
        parsed = json.loads(result)

        assert parsed["truncated"] is False
        assert parsed["returned"] == 1
        assert parsed["total"] == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_history_json_keeps_most_recent_tail_when_capped(
        self, ctx: MagicMock
    ) -> None:
        """IEM ASOS data is oldest-first (verified live against the real
        mesonet.agron.iastate.edu API: rows for a station ascend in time
        from the requested start date to the end date). So when
        winds_get_history's JSON output is capped, it must keep the TAIL
        (the most recent rows), not the head — keeping the head would
        silently drop the newest data in favor of the oldest."""
        from winds_mcp.tools.observations import winds_get_history

        header = "station,valid,drct,sknt,gust\n"
        rows = "".join(f"JFK,2025-01-01 {h:02d}:00,90.00,{h}.00,M\n" for h in range(24))
        respx.get(url__regex=r".*/cgi-bin/request/asos.py").mock(
            return_value=httpx.Response(200, text=header + rows)
        )

        result = await winds_get_history(
            ctx,
            station_id="KJFK",
            start_date="2025-01-01",
            end_date="2025-01-02",
            response_format="json",
            max_records=5,
        )
        parsed = json.loads(result)

        assert parsed["truncated"] is True
        assert parsed["returned"] == 5
        assert parsed["total"] == 24
        assert "hint" in parsed
        kept_hours = [r["valid"][-5:-3] for r in parsed["data"]["results"]]
        # The most recent 5 hours (19 through 23), in original chronological order.
        assert kept_hours == ["19", "20", "21", "22", "23"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_observations_json_keeps_most_recent_head_when_capped(
        self, ctx: MagicMock
    ) -> None:
        """NWS /observations returns data newest-first (verified live
        against api.weather.gov: features descend in time from the request
        end back toward the start). So when winds_get_observations' JSON
        output is capped, it must keep the HEAD (the first N items, which
        are the most recent), unlike the oldest-first IEM source above."""
        from winds_mcp.tools.observations import winds_get_observations

        features = [
            {
                "properties": {
                    "timestamp": f"2025-01-01T{23 - h:02d}:00:00+00:00",
                    "windSpeed": {"value": float(h)},
                }
            }
            for h in range(10)
        ]
        respx.get(url__regex=r".*/stations/.*/observations\b").mock(
            return_value=httpx.Response(
                200, json={"type": "FeatureCollection", "features": features}
            )
        )

        result = await winds_get_observations(
            ctx,
            station_id="KJFK",
            hours=24,
            response_format="json",
            max_records=3,
        )
        parsed = json.loads(result)

        assert parsed["truncated"] is True
        assert parsed["returned"] == 3
        assert parsed["total"] == 10
        kept_hours = [
            f["properties"]["timestamp"][11:13] for f in parsed["data"]["features"]
        ]
        # Newest-first source: the kept head is the 3 most recent hours.
        assert kept_hours == ["23", "22", "21"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_history_markdown_keeps_most_recent_200_rows(
        self, ctx: MagicMock
    ) -> None:
        """The markdown table for winds_get_history must keep the most
        recent 200 rows out of a longer oldest-first series, not the
        earliest 200 (the original bug: `results[:200]` on oldest-first
        data kept the oldest rows and mislabeled them "first 200")."""
        from winds_mcp.tools.observations import winds_get_history

        header = "station,valid,drct,sknt,gust\n"
        # 250 hourly rows spanning just over 10 days, strictly increasing in time.
        rows = "".join(
            f"JFK,2025-01-{1 + h // 24:02d} {h % 24:02d}:00,90.00,{h % 60}.00,M\n"
            for h in range(250)
        )
        respx.get(url__regex=r".*/cgi-bin/request/asos.py").mock(
            return_value=httpx.Response(200, text=header + rows)
        )

        result = await winds_get_history(
            ctx, station_id="KJFK", start_date="2025-01-01", end_date="2025-01-12"
        )

        assert "Showing most recent 200 of 250" in result
        # The last row (index 249) must be present; an early row that fell
        # outside the kept tail (e.g. index 10) must not be.
        assert "2025-01-11 09:00" in result  # row 249 -> day 11, hour 9
        assert "2025-01-01 10:00" not in result  # row 10, outside the tail


class TestWindsListStationsExtras:
    """Additional coverage for winds_list_stations output discipline."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_json_carries_state_context(self, ctx: MagicMock) -> None:
        """The JSON envelope carries the requested state as context."""
        from winds_mcp.tools.stations import winds_list_stations

        fixture = _load_fixture("nws_stations_ny.json")
        respx.get(f"{NWS_API_BASE}/stations").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await winds_list_stations(ctx, state="NY", response_format="json")
        parsed = json.loads(result)

        assert parsed["state"] == "NY"


class TestWindsFindNearestStationsExtras:
    """Coverage for the client/tool split that fixed the lost-total bug in
    winds_find_nearest_stations (the client used to trim to `limit` itself,
    discarding how many stations NWS actually returned)."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_json_reports_total_before_trim(self, ctx: MagicMock) -> None:
        """Requesting a small limit against a larger NWS result reports the
        true total and flags truncation, instead of silently reporting
        returned==total==limit."""
        from winds_mcp.tools.stations import winds_find_nearest_stations

        fixture = _load_fixture("nws_nearest_stations.json")
        respx.get(url__regex=r".*/points/.*/stations").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await winds_find_nearest_stations(
            ctx, latitude=40.7, longitude=-74.0, limit=1, response_format="json"
        )
        parsed = json.loads(result)

        assert parsed["total"] >= parsed["returned"]
        assert parsed["returned"] == 1
        if parsed["total"] > 1:
            assert parsed["truncated"] is True
            assert "hint" in parsed
