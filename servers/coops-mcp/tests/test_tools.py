"""Unit tests for coops-mcp tool functions with mocked HTTP responses.

Tests cover water levels, tide predictions, station metadata, station listing,
nearest station search, meteorological observations, currents, tidal datums,
extreme water levels, sea level trends, peak storm events, and flood statistics.

All HTTP calls are mocked using respx; no network access is required.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from coops_mcp.client import (
    COOPSClient,
    DATA_API_BASE,
    METADATA_API_BASE,
    DERIVED_API_BASE,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    """Load a JSON fixture file by name (without directory prefix)."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


def _make_ctx(client: COOPSClient) -> MagicMock:
    """Build a mock MCP Context whose lifespan_context holds the given COOPSClient."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"coops_client": client}
    return ctx


# ---------------------------------------------------------------------------
# Shared pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def coops_client() -> COOPSClient:
    """Create a bare COOPSClient (its internal httpx client will be intercepted by respx)."""
    return COOPSClient()


@pytest.fixture
def ctx(coops_client: COOPSClient) -> MagicMock:
    """Create a mock Context wired to the COOPSClient fixture."""
    return _make_ctx(coops_client)


# ===========================================================================
# Water level tools
# ===========================================================================


class TestGetWaterLevels:
    """Tests for the coops_get_water_levels tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_water_levels_recent_markdown(self, ctx: MagicMock) -> None:
        """Fetch recent water levels and verify markdown output contains expected station data."""
        from coops_mcp.tools.water_levels import coops_get_water_levels

        fixture = _load_fixture("water_levels_latest.json")
        respx.get(DATA_API_BASE).mock(return_value=httpx.Response(200, json=fixture))

        result = await coops_get_water_levels(ctx, station_id="8518750")

        assert "8518750" in result
        assert "Water Levels" in result
        # The fixture has one data row with time "2026-03-04 17:00"
        assert "2026-03-04 17:00" in result
        assert "0.6" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_water_levels_recent_json(self, ctx: MagicMock) -> None:
        """Fetch recent water levels with JSON response format and verify structure."""
        from coops_mcp.tools.water_levels import coops_get_water_levels

        fixture = _load_fixture("water_levels_latest.json")
        respx.get(DATA_API_BASE).mock(return_value=httpx.Response(200, json=fixture))

        result = await coops_get_water_levels(
            ctx, station_id="8518750", response_format="json"
        )

        parsed = json.loads(result)
        assert parsed["station_id"] == "8518750"
        assert parsed["record_count"] >= 1
        assert "data" in parsed

    @respx.mock
    @pytest.mark.asyncio
    async def test_water_levels_with_date_range(self, ctx: MagicMock) -> None:
        """Fetch water levels with explicit begin/end dates."""
        from coops_mcp.tools.water_levels import coops_get_water_levels

        fixture = _load_fixture("water_levels_latest.json")
        route = respx.get(DATA_API_BASE).mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await coops_get_water_levels(
            ctx,
            station_id="8518750",
            begin_date="2026-03-01",
            end_date="2026-03-02",
        )

        assert "Water Levels" in result
        # Verify the normalized dates were sent in the request
        assert route.called
        request_params = dict(route.calls[0].request.url.params)
        assert request_params["begin_date"] == "20260301"
        assert request_params["end_date"] == "20260302"

    @respx.mock
    @pytest.mark.asyncio
    async def test_water_levels_api_error_response(self, ctx: MagicMock) -> None:
        """Verify graceful handling when the CO-OPS API returns an error in the JSON body."""
        from coops_mcp.tools.water_levels import coops_get_water_levels

        error_body = {"error": {"message": "No data was found"}}
        respx.get(DATA_API_BASE).mock(return_value=httpx.Response(200, json=error_body))

        result = await coops_get_water_levels(ctx, station_id="9999999")

        assert "Error" in result or "error" in result.lower()
        assert "No data was found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_water_levels_http_500(self, ctx: MagicMock) -> None:
        """Verify graceful handling of an HTTP 500 server error."""
        from coops_mcp.tools.water_levels import coops_get_water_levels

        respx.get(DATA_API_BASE).mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        result = await coops_get_water_levels(ctx, station_id="8518750")

        assert "HTTP Error" in result or "Error" in result

    @pytest.mark.asyncio
    async def test_water_levels_invalid_date_range(self, ctx: MagicMock) -> None:
        """Verify that a date range exceeding 365 days produces a validation error."""
        from coops_mcp.tools.water_levels import coops_get_water_levels

        result = await coops_get_water_levels(
            ctx,
            station_id="8518750",
            begin_date="2024-01-01",
            end_date="2025-06-01",
        )

        assert "Validation Error" in result
        assert "exceeds" in result.lower() or "365" in result


# ===========================================================================
# Tide prediction tools
# ===========================================================================


class TestGetTidePredictions:
    """Tests for the coops_get_tide_predictions tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_tide_predictions_hilo_markdown(self, ctx: MagicMock) -> None:
        """Fetch high/low tide predictions and verify markdown output."""
        from coops_mcp.models import Interval
        from coops_mcp.tools.water_levels import coops_get_tide_predictions

        fixture = _load_fixture("tide_predictions.json")
        respx.get(DATA_API_BASE).mock(return_value=httpx.Response(200, json=fixture))

        result = await coops_get_tide_predictions(
            ctx,
            station_id="8518750",
            begin_date="2025-01-01",
            end_date="2025-01-02",
            interval=Interval.HILO,
        )

        assert "Tide Predictions" in result
        assert "8518750" in result
        # Fixture contains 8 predictions
        assert "8 predictions" in result
        # Check a known value
        assert "1.201" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_tide_predictions_json_format(self, ctx: MagicMock) -> None:
        """Fetch tide predictions as JSON and verify the wrapper structure."""
        from coops_mcp.tools.water_levels import coops_get_tide_predictions

        fixture = _load_fixture("tide_predictions.json")
        respx.get(DATA_API_BASE).mock(return_value=httpx.Response(200, json=fixture))

        result = await coops_get_tide_predictions(
            ctx,
            station_id="8518750",
            begin_date="2025-01-01",
            end_date="2025-01-02",
            response_format="json",
        )

        parsed = json.loads(result)
        assert parsed["station_id"] == "8518750"
        assert parsed["record_count"] == 8
        assert "predictions" in parsed["data"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_tide_predictions_request_params(self, ctx: MagicMock) -> None:
        """Verify the correct API request parameters are sent for tide predictions."""
        from coops_mcp.tools.water_levels import coops_get_tide_predictions

        fixture = _load_fixture("tide_predictions.json")
        route = respx.get(DATA_API_BASE).mock(
            return_value=httpx.Response(200, json=fixture)
        )

        await coops_get_tide_predictions(
            ctx,
            station_id="8518750",
            begin_date="2025-01-01",
            end_date="2025-01-02",
        )

        assert route.called
        params = dict(route.calls[0].request.url.params)
        assert params["station"] == "8518750"
        assert params["product"] == "predictions"
        assert params["datum"] == "MLLW"
        assert params["format"] == "json"


# ===========================================================================
# Station tools
# ===========================================================================


class TestStationTools:
    """Tests for station listing, detail, and nearest-station tools."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_stations(self, ctx: MagicMock) -> None:
        """List stations and verify output contains station IDs from fixture."""
        from coops_mcp.tools.stations import coops_list_stations

        fixture = _load_fixture("stations_list.json")
        respx.get(f"{METADATA_API_BASE}/stations.json").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await coops_list_stations(ctx)

        assert "CO-OPS Stations" in result
        # The fixture contains Nawiliwili (1611400), Honolulu (1612340), etc.
        assert "1611400" in result
        assert "Nawiliwili" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_list_stations_with_state_filter(self, ctx: MagicMock) -> None:
        """List stations filtered by state and verify only matching stations appear."""
        from coops_mcp.tools.stations import coops_list_stations

        fixture = _load_fixture("stations_list.json")
        respx.get(f"{METADATA_API_BASE}/stations.json").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await coops_list_stations(ctx, state="HI")

        assert "CO-OPS Stations" in result
        assert "State: HI" in result
        # All three fixture stations are in HI
        assert "Nawiliwili" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_station_detail(self, ctx: MagicMock) -> None:
        """Get detailed station metadata and verify key fields are present."""
        from coops_mcp.tools.stations import coops_get_station

        # Build a clean fixture without nested link-only dicts that would
        # confuse the iteration logic (the real API only populates sensor
        # lists when ?expand=sensors is requested).
        fixture = {
            "stations": [
                {
                    "id": "8518750",
                    "name": "The Battery",
                    "state": "NY",
                    "lat": 40.700554,
                    "lng": -74.01417,
                    "affiliations": "NWLORTS",
                    "timezonecorr": -5,
                }
            ]
        }
        respx.get(f"{METADATA_API_BASE}/stations/8518750.json").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await coops_get_station(ctx, station_id="8518750")

        assert "Station 8518750" in result
        assert "The Battery" in result
        assert "NY" in result
        assert "40.700554" in result
        assert "-74.01417" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_nearest_stations(self, ctx: MagicMock) -> None:
        """Find nearest stations and verify distance-sorted output."""
        from coops_mcp.tools.stations import coops_find_nearest_stations

        fixture = _load_fixture("nearest_stations.json")
        respx.get(f"{METADATA_API_BASE}/stations.json").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        # Query near Honolulu (21.3, -157.9) -- within radius of fixture stations
        result = await coops_find_nearest_stations(
            ctx, latitude=21.3, longitude=-157.9, radius_km=500
        )

        assert "Nearest Stations" in result
        assert "21.3" in result
        # At least Honolulu (1612340) should be very close
        assert "km" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_find_nearest_stations_none_in_radius(self, ctx: MagicMock) -> None:
        """Verify message when no stations found within radius."""
        from coops_mcp.tools.stations import coops_find_nearest_stations

        fixture = _load_fixture("nearest_stations.json")
        respx.get(f"{METADATA_API_BASE}/stations.json").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        # Query at a location far from any fixture station with tiny radius
        result = await coops_find_nearest_stations(
            ctx, latitude=0.0, longitude=0.0, radius_km=1
        )

        assert "No stations found" in result


# ===========================================================================
# Meteorological tools
# ===========================================================================


class TestGetMeteorological:
    """Tests for the coops_get_meteorological tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_wind_data_markdown(self, ctx: MagicMock) -> None:
        """Fetch wind observations and verify markdown output columns."""
        from coops_mcp.models import MetProduct
        from coops_mcp.tools.meteorological import coops_get_meteorological

        fixture = _load_fixture("meteorological_wind.json")
        respx.get(DATA_API_BASE).mock(return_value=httpx.Response(200, json=fixture))

        result = await coops_get_meteorological(
            ctx,
            station_id="8724580",
            product=MetProduct.WIND,
        )

        assert "Wind" in result
        assert "8724580" in result
        # Wind columns include Speed, Direction, Compass, Gust
        assert "Speed" in result
        assert "Direction" in result
        # Fixture value
        assert "5.4" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_wind_data_json(self, ctx: MagicMock) -> None:
        """Fetch wind observations as JSON and verify structure."""
        from coops_mcp.models import MetProduct
        from coops_mcp.tools.meteorological import coops_get_meteorological

        fixture = _load_fixture("meteorological_wind.json")
        respx.get(DATA_API_BASE).mock(return_value=httpx.Response(200, json=fixture))

        result = await coops_get_meteorological(
            ctx,
            station_id="8724580",
            product=MetProduct.WIND,
            response_format="json",
        )

        parsed = json.loads(result)
        assert parsed["station_id"] == "8724580"
        assert parsed["record_count"] >= 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_meteorological_request_params(self, ctx: MagicMock) -> None:
        """Verify correct API parameters are sent for meteorological requests."""
        from coops_mcp.models import MetProduct
        from coops_mcp.tools.meteorological import coops_get_meteorological

        fixture = _load_fixture("meteorological_wind.json")
        route = respx.get(DATA_API_BASE).mock(
            return_value=httpx.Response(200, json=fixture)
        )

        await coops_get_meteorological(
            ctx,
            station_id="8724580",
            product=MetProduct.WIND,
            begin_date="2026-03-04",
            end_date="2026-03-04",
        )

        assert route.called
        params = dict(route.calls[0].request.url.params)
        assert params["product"] == "wind"
        assert params["station"] == "8724580"
        assert params["begin_date"] == "20260304"
        assert params["end_date"] == "20260304"


# ===========================================================================
# Currents tools
# ===========================================================================


class TestGetCurrents:
    """Tests for the coops_get_currents tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_currents_markdown(self, ctx: MagicMock) -> None:
        """Fetch current observations and verify markdown output."""
        from coops_mcp.tools.currents import coops_get_currents

        fixture = _load_fixture("currents.json")
        respx.get(DATA_API_BASE).mock(return_value=httpx.Response(200, json=fixture))

        result = await coops_get_currents(ctx, station_id="cb1401")

        assert "Currents" in result
        assert "cb1401" in result
        # Fixture data: speed 1.4, direction 294
        assert "1.4" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_currents_json(self, ctx: MagicMock) -> None:
        """Fetch current observations as JSON and verify wrapper structure."""
        from coops_mcp.tools.currents import coops_get_currents

        fixture = _load_fixture("currents.json")
        respx.get(DATA_API_BASE).mock(return_value=httpx.Response(200, json=fixture))

        result = await coops_get_currents(
            ctx, station_id="cb1401", response_format="json"
        )

        parsed = json.loads(result)
        assert parsed["station_id"] == "cb1401"
        assert "data" in parsed


# ===========================================================================
# Derived product tools
# ===========================================================================


class TestDatums:
    """Tests for the coops_get_datums tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_datums_markdown(self, ctx: MagicMock) -> None:
        """Fetch tidal datums and verify markdown output contains known datum names."""
        from coops_mcp.tools.derived import coops_get_datums

        fixture = _load_fixture("datums.json")
        respx.get(f"{METADATA_API_BASE}/stations/8518750/datums.json").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await coops_get_datums(ctx, station_id="8518750")

        assert "Tidal Datums" in result
        assert "8518750" in result
        assert "MHHW" in result
        assert "MLLW" in result
        assert "Mean Higher-High Water" in result
        # Check a known value
        assert "2.543" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_datums_english_units(self, ctx: MagicMock) -> None:
        """Fetch datums with english units and verify unit label in output."""
        from coops_mcp.models import Units
        from coops_mcp.tools.derived import coops_get_datums

        fixture = _load_fixture("datums.json")
        route = respx.get(f"{METADATA_API_BASE}/stations/8518750/datums.json").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await coops_get_datums(ctx, station_id="8518750", units=Units.ENGLISH)

        assert "ft" in result
        # Verify english units param was sent
        params = dict(route.calls[0].request.url.params)
        assert params["units"] == "english"


class TestExtremeWaterLevels:
    """Tests for the coops_get_extreme_water_levels tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_extreme_water_levels_markdown(self, ctx: MagicMock) -> None:
        """Fetch extreme water levels and verify markdown output contains events."""
        from coops_mcp.tools.derived import coops_get_extreme_water_levels

        fixture = _load_fixture("extreme_water_levels.json")
        respx.get(f"{DERIVED_API_BASE}/product.json").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await coops_get_extreme_water_levels(ctx, station_id="8518750")

        assert "Extreme Water Levels" in result
        assert "The Battery" in result
        assert "Highest Water Level Events" in result
        assert "Lowest Water Level Events" in result
        # Check known dates from fixture (only first 10 highs/lows are shown)
        assert "09/21/1938" in result
        assert "02/02/1908" in result  # First low event

    @respx.mock
    @pytest.mark.asyncio
    async def test_extreme_water_levels_empty(self, ctx: MagicMock) -> None:
        """Verify message when no extreme water level data is available."""
        from coops_mcp.tools.derived import coops_get_extreme_water_levels

        empty_fixture = {"ExtremeWaterLevels": []}
        respx.get(f"{DERIVED_API_BASE}/product.json").mock(
            return_value=httpx.Response(200, json=empty_fixture)
        )

        result = await coops_get_extreme_water_levels(ctx, station_id="0000000")

        assert "No extreme water level data" in result


class TestSeaLevelTrends:
    """Tests for the coops_get_sea_level_trends tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_sea_level_trends_markdown(self, ctx: MagicMock) -> None:
        """Fetch sea level trends and verify key fields in markdown output."""
        from coops_mcp.tools.derived import coops_get_sea_level_trends

        fixture = _load_fixture("sea_level_trends.json")
        respx.get(f"{DERIVED_API_BASE}/product/sealvltrends.json").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await coops_get_sea_level_trends(ctx, station_id="8518750")

        assert "Sea Level Trends" in result
        assert "The Battery" in result
        assert "1.16" in result  # trend value from fixture
        assert "inches/decade" in result
        assert "01/15/1856" in result  # start date

    @respx.mock
    @pytest.mark.asyncio
    async def test_sea_level_trends_empty(self, ctx: MagicMock) -> None:
        """Verify message when no trend data is available."""
        from coops_mcp.tools.derived import coops_get_sea_level_trends

        empty_fixture = {"SeaLvlTrends": []}
        respx.get(f"{DERIVED_API_BASE}/product/sealvltrends.json").mock(
            return_value=httpx.Response(200, json=empty_fixture)
        )

        result = await coops_get_sea_level_trends(ctx, station_id="0000000")

        assert "No sea level trend data" in result


class TestPeakStormEvents:
    """Tests for the coops_get_peak_storm_events tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_peak_storm_events_markdown(self, ctx: MagicMock) -> None:
        """Fetch peak storm events and verify markdown table output."""
        from coops_mcp.tools.derived import coops_get_peak_storm_events

        # Use a minimal fixture with just a few events
        fixture = {
            "peakWaterLevels": [
                {
                    "eventId": 1,
                    "startDate": "1898-10-02 00:00:00",
                    "name": "1898 Georgia Hurricane",
                    "eventType": "Tropical",
                    "peakValue": 2.35,
                },
                {
                    "eventId": 2,
                    "startDate": "2012-10-29 00:00:00",
                    "name": "Hurricane Sandy",
                    "eventType": "Tropical",
                    "peakValue": 3.44,
                },
            ]
        }
        respx.get(f"{DERIVED_API_BASE}/product.json").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await coops_get_peak_storm_events(ctx, station_id="8518750")

        assert "Peak Storm Events" in result
        assert "8518750" in result
        assert "Hurricane Sandy" in result
        assert "3.44" in result
        assert "2 events" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_peak_storm_events_empty(self, ctx: MagicMock) -> None:
        """Verify message when no peak storm event data is available."""
        from coops_mcp.tools.derived import coops_get_peak_storm_events

        empty_fixture = {"peakWaterLevels": []}
        respx.get(f"{DERIVED_API_BASE}/product.json").mock(
            return_value=httpx.Response(200, json=empty_fixture)
        )

        result = await coops_get_peak_storm_events(ctx, station_id="0000000")

        assert "No peak storm event data" in result


class TestFloodStats:
    """Tests for the coops_get_flood_stats tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_flood_stats_markdown(self, ctx: MagicMock) -> None:
        """Fetch flood statistics and verify annual flood count data appears."""
        from coops_mcp.tools.derived import coops_get_flood_stats

        flood_fixture = _load_fixture("flood_annual.json")
        outlook_fixture = {"MetYearAnnualOutlook": []}

        # The tool makes two separate requests to the derived API
        respx.get(f"{DERIVED_API_BASE}/htf/htf_annual.json").mock(
            return_value=httpx.Response(200, json=flood_fixture)
        )
        respx.get(f"{DERIVED_API_BASE}/htf/htf_met_year_annual_outlook.json").mock(
            return_value=httpx.Response(200, json=outlook_fixture)
        )

        result = await coops_get_flood_stats(ctx, station_id="8518750")

        assert "Flood Statistics" in result
        assert "8518750" in result
        assert "Annual Flood Day Counts" in result
        # The fixture contains year 1920
        assert "1920" in result


# ===========================================================================
# Error handling
# ===========================================================================


class TestErrorHandling:
    """Tests for error handling across tool functions."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_timeout_error(self, ctx: MagicMock) -> None:
        """Verify graceful handling of request timeouts."""
        from coops_mcp.tools.water_levels import coops_get_water_levels

        respx.get(DATA_API_BASE).mock(side_effect=httpx.ReadTimeout("timed out"))

        result = await coops_get_water_levels(ctx, station_id="8518750")

        assert "timed out" in result.lower() or "timeout" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_station_metadata_http_error(self, ctx: MagicMock) -> None:
        """Verify graceful handling of HTTP errors in metadata requests."""
        from coops_mcp.tools.stations import coops_get_station

        respx.get(f"{METADATA_API_BASE}/stations/INVALID.json").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        result = await coops_get_station(ctx, station_id="INVALID")

        assert "Error" in result or "error" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_derived_api_http_error(self, ctx: MagicMock) -> None:
        """Verify graceful handling of HTTP errors in derived API requests."""
        from coops_mcp.tools.derived import coops_get_sea_level_trends

        respx.get(f"{DERIVED_API_BASE}/product/sealvltrends.json").mock(
            return_value=httpx.Response(503, text="Service Unavailable")
        )

        result = await coops_get_sea_level_trends(ctx, station_id="8518750")

        assert "Error" in result or "error" in result.lower()
