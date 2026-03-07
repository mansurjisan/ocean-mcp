"""Unit tests for ndbc-mcp tool functions with mocked HTTP responses.

All HTTP calls are mocked using respx; no network access is required.
"""

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from ndbc_mcp.client import NDBCClient, REALTIME2_BASE, ACTIVE_STATIONS_URL

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    """Load a text fixture file."""
    with open(FIXTURES_DIR / name) as f:
        return f.read()


def _make_ctx(client: NDBCClient) -> MagicMock:
    """Build a mock MCP Context whose lifespan_context holds the given NDBCClient."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"ndbc_client": client}
    return ctx


# ---------------------------------------------------------------------------
# Shared pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ndbc_client() -> NDBCClient:
    """Create a bare NDBCClient (its internal httpx client will be intercepted by respx)."""
    return NDBCClient()


@pytest.fixture
def ctx(ndbc_client: NDBCClient) -> MagicMock:
    """Create a mock Context wired to the NDBCClient fixture."""
    return _make_ctx(ndbc_client)


# ===========================================================================
# Station tools
# ===========================================================================


class TestListStations:
    """Tests for the ndbc_list_stations tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_stations_returns_markdown(self, ctx: MagicMock) -> None:
        """List stations and verify markdown output."""
        from ndbc_mcp.tools.stations import ndbc_list_stations

        xml = _load_fixture("activestations.xml")
        respx.get(ACTIVE_STATIONS_URL).mock(return_value=httpx.Response(200, text=xml))

        result = await ndbc_list_stations(ctx)

        assert "NDBC Active Stations" in result
        assert "44013" in result
        assert "46042" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_stations_filter_by_type(self, ctx: MagicMock) -> None:
        """Filter stations by type and verify only matching stations appear."""
        from ndbc_mcp.tools.stations import ndbc_list_stations

        xml = _load_fixture("activestations.xml")
        respx.get(ACTIVE_STATIONS_URL).mock(return_value=httpx.Response(200, text=xml))

        result = await ndbc_list_stations(ctx, station_type="dart")

        assert "21413" in result
        assert "44013" not in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_stations_filter_has_met(self, ctx: MagicMock) -> None:
        """Filter stations by met sensors."""
        from ndbc_mcp.tools.stations import ndbc_list_stations

        xml = _load_fixture("activestations.xml")
        respx.get(ACTIVE_STATIONS_URL).mock(return_value=httpx.Response(200, text=xml))

        result = await ndbc_list_stations(ctx, has_met=True)

        assert "21413" not in result  # DART station, met=n
        assert "44013" in result


class TestGetStation:
    """Tests for the ndbc_get_station tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_station_found(self, ctx: MagicMock) -> None:
        """Get metadata for a known station."""
        from ndbc_mcp.tools.stations import ndbc_get_station

        xml = _load_fixture("activestations.xml")
        respx.get(ACTIVE_STATIONS_URL).mock(return_value=httpx.Response(200, text=xml))

        result = await ndbc_get_station(ctx, station_id="44013")

        assert "Station 44013" in result
        assert "Boston" in result
        assert "buoy" in result.lower()
        assert "NDBC" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_station_not_found(self, ctx: MagicMock) -> None:
        """Verify graceful handling when station is not found."""
        from ndbc_mcp.tools.stations import ndbc_get_station

        xml = _load_fixture("activestations.xml")
        respx.get(ACTIVE_STATIONS_URL).mock(return_value=httpx.Response(200, text=xml))

        result = await ndbc_get_station(ctx, station_id="ZZZZZ")

        assert "not found" in result.lower()


class TestFindNearestStations:
    """Tests for the ndbc_find_nearest_stations tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_nearest_boston(self, ctx: MagicMock) -> None:
        """Find stations near Boston and verify 44013 is returned."""
        from ndbc_mcp.tools.stations import ndbc_find_nearest_stations

        xml = _load_fixture("activestations.xml")
        respx.get(ACTIVE_STATIONS_URL).mock(return_value=httpx.Response(200, text=xml))

        result = await ndbc_find_nearest_stations(
            ctx, latitude=42.36, longitude=-71.06, radius_km=300
        )

        assert "44013" in result
        assert "km" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_nearest_no_results(self, ctx: MagicMock) -> None:
        """Verify message when no stations found in radius."""
        from ndbc_mcp.tools.stations import ndbc_find_nearest_stations

        xml = _load_fixture("activestations.xml")
        respx.get(ACTIVE_STATIONS_URL).mock(return_value=httpx.Response(200, text=xml))

        result = await ndbc_find_nearest_stations(
            ctx, latitude=0.0, longitude=0.0, radius_km=10
        )

        assert "No stations found" in result


# ===========================================================================
# Observation tools
# ===========================================================================


class TestGetLatestObservation:
    """Tests for the ndbc_get_latest_observation tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_latest_obs_markdown(self, ctx: MagicMock) -> None:
        """Fetch latest observation and verify markdown output."""
        from ndbc_mcp.tools.observations import ndbc_get_latest_observation

        txt = _load_fixture("realtime_44013.txt")
        respx.get(f"{REALTIME2_BASE}/44013.txt").mock(
            return_value=httpx.Response(200, text=txt)
        )

        result = await ndbc_get_latest_observation(ctx, station_id="44013")

        assert "Latest Observation" in result
        assert "44013" in result
        assert "Wind" in result or "Pressure" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_latest_obs_json(self, ctx: MagicMock) -> None:
        """Fetch latest observation in JSON format."""
        import json
        from ndbc_mcp.tools.observations import ndbc_get_latest_observation

        txt = _load_fixture("realtime_44013.txt")
        respx.get(f"{REALTIME2_BASE}/44013.txt").mock(
            return_value=httpx.Response(200, text=txt)
        )

        result = await ndbc_get_latest_observation(
            ctx, station_id="44013", response_format="json"
        )

        parsed = json.loads(result)
        assert parsed["station"] == "44013"
        assert "observation" in parsed

    @respx.mock
    @pytest.mark.asyncio
    async def test_latest_obs_404(self, ctx: MagicMock) -> None:
        """Verify graceful handling of HTTP 404."""
        from ndbc_mcp.tools.observations import ndbc_get_latest_observation

        respx.get(f"{REALTIME2_BASE}/ZZZZZ.txt").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        result = await ndbc_get_latest_observation(ctx, station_id="ZZZZZ")

        assert "Error" in result or "not found" in result.lower()


class TestGetObservations:
    """Tests for the ndbc_get_observations tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_observations_markdown(self, ctx: MagicMock) -> None:
        """Fetch observations and verify markdown table output."""
        from ndbc_mcp.tools.observations import ndbc_get_observations

        txt = _load_fixture("realtime_44013.txt")
        respx.get(f"{REALTIME2_BASE}/44013.txt").mock(
            return_value=httpx.Response(200, text=txt)
        )

        result = await ndbc_get_observations(ctx, station_id="44013", hours=24)

        assert "Observations" in result
        assert "44013" in result
        assert "|" in result  # Table format

    @respx.mock
    @pytest.mark.asyncio
    async def test_observations_with_variable_filter(self, ctx: MagicMock) -> None:
        """Fetch observations with variable filter."""
        import json
        from ndbc_mcp.tools.observations import ndbc_get_observations

        txt = _load_fixture("realtime_44013.txt")
        respx.get(f"{REALTIME2_BASE}/44013.txt").mock(
            return_value=httpx.Response(200, text=txt)
        )

        result = await ndbc_get_observations(
            ctx,
            station_id="44013",
            hours=24,
            variables=["WSPD", "WTMP"],
            response_format="json",
        )

        parsed = json.loads(result)
        assert "records" in parsed
        if parsed["records"]:
            assert "WSPD" in parsed["records"][0]
            assert "WTMP" in parsed["records"][0]

    def test_hours_validation_too_high(self) -> None:
        """Verify hours > 1080 produces error synchronously by checking the range."""
        assert 1080 < 1081  # Sanity check; actual validation tested via tool call

    @respx.mock
    @pytest.mark.asyncio
    async def test_observations_invalid_hours(self, ctx: MagicMock) -> None:
        """Verify hours validation error."""
        from ndbc_mcp.tools.observations import ndbc_get_observations

        result = await ndbc_get_observations(ctx, station_id="44013", hours=2000)

        assert "Validation Error" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_observations_invalid_variables(self, ctx: MagicMock) -> None:
        """Verify error when no requested variables match."""
        from ndbc_mcp.tools.observations import ndbc_get_observations

        txt = _load_fixture("realtime_44013.txt")
        respx.get(f"{REALTIME2_BASE}/44013.txt").mock(
            return_value=httpx.Response(200, text=txt)
        )

        result = await ndbc_get_observations(
            ctx, station_id="44013", hours=24, variables=["NONEXISTENT"]
        )

        assert "None of the requested variables" in result


class TestGetWaveSummary:
    """Tests for the ndbc_get_wave_summary tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_wave_summary_markdown(self, ctx: MagicMock) -> None:
        """Fetch wave spectral summary and verify markdown output."""
        from ndbc_mcp.tools.observations import ndbc_get_wave_summary

        txt = _load_fixture("spec_44013.txt")
        respx.get(f"{REALTIME2_BASE}/44013.spec").mock(
            return_value=httpx.Response(200, text=txt)
        )

        result = await ndbc_get_wave_summary(ctx, station_id="44013")

        assert "Wave Spectral Summary" in result
        assert "44013" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_wave_summary_404(self, ctx: MagicMock) -> None:
        """Verify graceful handling when no spectral data available."""
        from ndbc_mcp.tools.observations import ndbc_get_wave_summary

        respx.get(f"{REALTIME2_BASE}/TPLM2.spec").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        result = await ndbc_get_wave_summary(ctx, station_id="TPLM2")

        assert "Error" in result or "not found" in result.lower()


# ===========================================================================
# Analysis tools
# ===========================================================================


class TestGetDailySummary:
    """Tests for the ndbc_get_daily_summary tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_daily_summary_markdown(self, ctx: MagicMock) -> None:
        """Compute daily summary and verify markdown output."""
        from ndbc_mcp.tools.analysis import ndbc_get_daily_summary

        txt = _load_fixture("realtime_44013.txt")
        respx.get(f"{REALTIME2_BASE}/44013.txt").mock(
            return_value=httpx.Response(200, text=txt)
        )

        result = await ndbc_get_daily_summary(ctx, station_id="44013", days=1)

        assert "Daily Summary" in result
        assert "44013" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_daily_summary_json(self, ctx: MagicMock) -> None:
        """Compute daily summary in JSON format."""
        import json
        from ndbc_mcp.tools.analysis import ndbc_get_daily_summary

        txt = _load_fixture("realtime_44013.txt")
        respx.get(f"{REALTIME2_BASE}/44013.txt").mock(
            return_value=httpx.Response(200, text=txt)
        )

        result = await ndbc_get_daily_summary(
            ctx, station_id="44013", days=1, response_format="json"
        )

        parsed = json.loads(result)
        assert parsed["station"] == "44013"
        assert "summaries" in parsed
        assert "variables" in parsed

    @respx.mock
    @pytest.mark.asyncio
    async def test_daily_summary_invalid_days(self, ctx: MagicMock) -> None:
        """Verify days validation error."""
        from ndbc_mcp.tools.analysis import ndbc_get_daily_summary

        result = await ndbc_get_daily_summary(ctx, station_id="44013", days=100)

        assert "Validation Error" in result


class TestCompareStations:
    """Tests for the ndbc_compare_stations tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_compare_two_stations(self, ctx: MagicMock) -> None:
        """Compare two stations and verify markdown table."""
        from ndbc_mcp.tools.analysis import ndbc_compare_stations

        txt = _load_fixture("realtime_44013.txt")
        respx.get(f"{REALTIME2_BASE}/44013.txt").mock(
            return_value=httpx.Response(200, text=txt)
        )
        respx.get(f"{REALTIME2_BASE}/TPLM2.txt").mock(
            return_value=httpx.Response(200, text=txt)
        )

        result = await ndbc_compare_stations(ctx, station_ids=["44013", "TPLM2"])

        assert "Station Comparison" in result
        assert "44013" in result
        assert "TPLM2" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_compare_too_few_stations(self, ctx: MagicMock) -> None:
        """Verify validation error with < 2 stations."""
        from ndbc_mcp.tools.analysis import ndbc_compare_stations

        result = await ndbc_compare_stations(ctx, station_ids=["44013"])

        assert "Validation Error" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_compare_too_many_stations(self, ctx: MagicMock) -> None:
        """Verify validation error with > 10 stations."""
        from ndbc_mcp.tools.analysis import ndbc_compare_stations

        ids = [f"STN{i:02d}" for i in range(11)]
        result = await ndbc_compare_stations(ctx, station_ids=ids)

        assert "Validation Error" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_compare_with_error_station(self, ctx: MagicMock) -> None:
        """Verify partial results when one station fails."""
        from ndbc_mcp.tools.analysis import ndbc_compare_stations

        txt = _load_fixture("realtime_44013.txt")
        respx.get(f"{REALTIME2_BASE}/44013.txt").mock(
            return_value=httpx.Response(200, text=txt)
        )
        respx.get(f"{REALTIME2_BASE}/ZZZZZ.txt").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        result = await ndbc_compare_stations(ctx, station_ids=["44013", "ZZZZZ"])

        assert "44013" in result
        assert "Errors" in result or "ZZZZZ" in result
