"""Comprehensive tests for nhc-mcp tool functions with mocked HTTP.

Tests all five tool functions:
- nhc_get_active_storms (active.py)
- nhc_get_forecast_track (forecast.py)
- nhc_get_storm_watches_warnings (forecast.py)
- nhc_get_best_track (history.py)
- nhc_search_storms (history.py)

Each tool is tested with:
- Mocked HTTP responses via respx
- Fixture data loaded from tests/fixtures/
- A mock Context object that provides the NHCClient
- Both markdown and JSON response formats
- Error handling scenarios
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from nhc_mcp.client import NHCClient, CURRENT_STORMS_URL, HURDAT2_URLS
from nhc_mcp.utils import ARCGIS_BASE_URL

# Import tool functions directly
from nhc_mcp.tools.active import nhc_get_active_storms
from nhc_mcp.tools.forecast import (
    nhc_get_forecast_track,
    nhc_get_storm_watches_warnings,
)
from nhc_mcp.tools.history import nhc_get_best_track, nhc_search_storms

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_fixture(name: str) -> str:
    """Load a fixture file as raw text."""
    return (FIXTURES_DIR / name).read_text()


def load_json_fixture(name: str) -> dict:
    """Load a fixture file as parsed JSON."""
    return json.loads(load_fixture(name))


def make_ctx(client: NHCClient) -> MagicMock:
    """Build a mock MCP Context that exposes the given NHCClient.

    The tool functions access the client via:
        ctx.request_context.lifespan_context["nhc_client"]
    """
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"nhc_client": client}
    return ctx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    """Create a fresh NHCClient and tear it down after the test."""
    c = NHCClient()
    yield c
    await c.close()


@pytest.fixture
def ctx(client):
    """Create a mock Context wrapping the NHCClient."""
    return make_ctx(client)


# ===========================================================================
# nhc_get_active_storms
# ===========================================================================


class TestGetActiveStorms:
    """Tests for the nhc_get_active_storms tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_no_active_storms_returns_informational_message(self, client):
        """When no storms are active the tool should return a helpful message."""
        fixture = load_json_fixture("active_storms.json")
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=fixture)
        )

        ctx = make_ctx(client)
        result = await nhc_get_active_storms(ctx)

        assert "No active tropical cyclones" in result
        assert "nhc_search_storms" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_active_storms_markdown_contains_table(self, client):
        """When storms exist the markdown output should contain a table with storm data."""
        fixture = load_json_fixture("active_storms_with_data.json")
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=fixture)
        )

        ctx = make_ctx(client)
        result = await nhc_get_active_storms(ctx)

        assert "## Active Tropical Cyclones" in result
        assert "Milton" in result
        assert "| Name |" in result
        assert "1 active storms returned" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_active_storms_json_format(self, client):
        """JSON format should return a parseable JSON string with storm data."""
        fixture = load_json_fixture("active_storms_with_data.json")
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=fixture)
        )

        ctx = make_ctx(client)
        result = await nhc_get_active_storms(ctx, response_format="json")

        data = json.loads(result)
        assert data["count"] == 1
        assert data["active_storms"][0]["name"] == "Milton"
        assert data["active_storms"][0]["id"] == "al052024"
        assert data["active_storms"][0]["classification"] == "HU"

    @respx.mock
    @pytest.mark.asyncio
    async def test_active_storms_json_includes_all_fields(self, client):
        """JSON output should include movement, pressure, wind, and advisory URL."""
        fixture = load_json_fixture("active_storms_with_data.json")
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=fixture)
        )

        ctx = make_ctx(client)
        result = await nhc_get_active_storms(ctx, response_format="json")

        storm = json.loads(result)["active_storms"][0]
        assert "movementDir" in storm
        assert "movementSpeed" in storm
        assert "pressure" in storm
        assert "wind" in storm
        assert "lastUpdate" in storm
        assert "advisory_url" in storm

    @respx.mock
    @pytest.mark.asyncio
    async def test_active_storms_http_error_returns_message(self, client):
        """An HTTP 500 error should be caught and returned as a user-friendly message."""
        respx.get(CURRENT_STORMS_URL).mock(return_value=httpx.Response(500))

        ctx = make_ctx(client)
        result = await nhc_get_active_storms(ctx)

        assert "Error" in result
        assert "HTTP 500" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_active_storms_timeout_returns_message(self, client):
        """A timeout should be caught and returned as a user-friendly message."""
        respx.get(CURRENT_STORMS_URL).mock(side_effect=httpx.ReadTimeout("timeout"))

        ctx = make_ctx(client)
        result = await nhc_get_active_storms(ctx)

        assert "timed out" in result


# ===========================================================================
# nhc_get_forecast_track
# ===========================================================================


class TestGetForecastTrack:
    """Tests for the nhc_get_forecast_track tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_forecast_track_markdown(self, client):
        """Forecast track markdown should contain a table with tau, lat, lon, wind data."""
        # Mock active storms to resolve binNumber
        storms_fixture = load_json_fixture("active_storms_with_data.json")
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=storms_fixture)
        )

        # Mock ArcGIS forecast points layer
        forecast_fixture = load_json_fixture("forecast_track.json")
        respx.get(url__startswith=ARCGIS_BASE_URL).mock(
            return_value=httpx.Response(200, json=forecast_fixture)
        )

        ctx = make_ctx(client)
        result = await nhc_get_forecast_track(ctx, storm_id="AL052024")

        assert "Forecast Track" in result
        assert "MILTON" in result
        assert "| Tau (hr) |" in result
        assert "3 forecast points returned" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_forecast_track_json_format(self, client):
        """Forecast track JSON should include storm_id, bin_number, and forecast_points."""
        storms_fixture = load_json_fixture("active_storms_with_data.json")
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=storms_fixture)
        )

        forecast_fixture = load_json_fixture("forecast_track.json")
        respx.get(url__startswith=ARCGIS_BASE_URL).mock(
            return_value=httpx.Response(200, json=forecast_fixture)
        )

        ctx = make_ctx(client)
        result = await nhc_get_forecast_track(
            ctx, storm_id="AL052024", response_format="json"
        )

        data = json.loads(result)
        assert data["storm_id"] == "AL052024"
        assert data["bin_number"] == "AT5"
        assert len(data["forecast_points"]) == 3

        # Verify sorting by tau
        taus = [int(pt["tau"]) for pt in data["forecast_points"]]
        assert taus == sorted(taus)

    @respx.mock
    @pytest.mark.asyncio
    async def test_forecast_track_json_point_fields(self, client):
        """Each forecast point should have the expected attribute fields."""
        storms_fixture = load_json_fixture("active_storms_with_data.json")
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=storms_fixture)
        )

        forecast_fixture = load_json_fixture("forecast_track.json")
        respx.get(url__startswith=ARCGIS_BASE_URL).mock(
            return_value=httpx.Response(200, json=forecast_fixture)
        )

        ctx = make_ctx(client)
        result = await nhc_get_forecast_track(
            ctx, storm_id="AL052024", response_format="json"
        )

        pt = json.loads(result)["forecast_points"][0]
        expected_keys = {
            "stormname",
            "tau",
            "datelbl",
            "lat",
            "lon",
            "maxwind",
            "gust",
            "mslp",
            "tcdvlp",
            "ssnum",
            "dvlbl",
            "advdate",
            "advisnum",
        }
        assert expected_keys.issubset(set(pt.keys()))

    @respx.mock
    @pytest.mark.asyncio
    async def test_forecast_track_storm_not_active(self, client):
        """Requesting a storm that is not active should return a helpful message."""
        storms_fixture = load_json_fixture("active_storms.json")  # empty
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=storms_fixture)
        )

        ctx = make_ctx(client)
        result = await nhc_get_forecast_track(ctx, storm_id="AL012099")

        assert "not found among active storms" in result
        assert "nhc_get_active_storms" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_forecast_track_empty_features(self, client):
        """When ArcGIS returns no features the tool should report advisory may be in preparation."""
        storms_fixture = load_json_fixture("active_storms_with_data.json")
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=storms_fixture)
        )

        empty_fixture = load_json_fixture("forecast_track_empty.json")
        respx.get(url__startswith=ARCGIS_BASE_URL).mock(
            return_value=httpx.Response(200, json=empty_fixture)
        )

        ctx = make_ctx(client)
        result = await nhc_get_forecast_track(ctx, storm_id="AL052024")

        assert "No forecast data available" in result
        assert "AL052024" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_forecast_track_arcgis_http_error(self, client):
        """An HTTP error from ArcGIS should be caught and reported to the user."""
        storms_fixture = load_json_fixture("active_storms_with_data.json")
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=storms_fixture)
        )

        respx.get(url__startswith=ARCGIS_BASE_URL).mock(
            return_value=httpx.Response(503)
        )

        ctx = make_ctx(client)
        result = await nhc_get_forecast_track(ctx, storm_id="AL052024")

        assert "Error" in result


# ===========================================================================
# nhc_get_storm_watches_warnings
# ===========================================================================


class TestGetStormWatchesWarnings:
    """Tests for the nhc_get_storm_watches_warnings tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_watches_warnings_markdown(self, client):
        """Watches/warnings markdown should list the warning types in a table."""
        storms_fixture = load_json_fixture("active_storms_with_data.json")
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=storms_fixture)
        )

        ww_fixture = load_json_fixture("watches_warnings.json")
        respx.get(url__startswith=ARCGIS_BASE_URL).mock(
            return_value=httpx.Response(200, json=ww_fixture)
        )

        ctx = make_ctx(client)
        result = await nhc_get_storm_watches_warnings(ctx, storm_id="AL052024")

        assert "Watches & Warnings" in result
        assert "MILTON" in result
        assert "| Watch/Warning Type |" in result
        assert "2 watch/warning segments returned" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_watches_warnings_json_format(self, client):
        """JSON output should include storm_id, bin_number, and watches_warnings array."""
        storms_fixture = load_json_fixture("active_storms_with_data.json")
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=storms_fixture)
        )

        ww_fixture = load_json_fixture("watches_warnings.json")
        respx.get(url__startswith=ARCGIS_BASE_URL).mock(
            return_value=httpx.Response(200, json=ww_fixture)
        )

        ctx = make_ctx(client)
        result = await nhc_get_storm_watches_warnings(
            ctx, storm_id="AL052024", response_format="json"
        )

        data = json.loads(result)
        assert data["storm_id"] == "AL052024"
        assert data["bin_number"] == "AT5"
        assert len(data["watches_warnings"]) == 2

        # Verify warning types
        types = [w["tcww"] for w in data["watches_warnings"]]
        assert "HWR" in types
        assert "TSW" in types

    @respx.mock
    @pytest.mark.asyncio
    async def test_watches_warnings_storm_not_active(self, client):
        """Non-active storm should return helpful guidance."""
        storms_fixture = load_json_fixture("active_storms.json")  # empty
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=storms_fixture)
        )

        ctx = make_ctx(client)
        result = await nhc_get_storm_watches_warnings(ctx, storm_id="AL012099")

        assert "not found among active storms" in result
        assert "nhc_get_active_storms" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_watches_warnings_no_warnings_in_effect(self, client):
        """When no watches/warnings exist the tool should explain why."""
        storms_fixture = load_json_fixture("active_storms_with_data.json")
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=storms_fixture)
        )

        empty_response = {"features": []}
        respx.get(url__startswith=ARCGIS_BASE_URL).mock(
            return_value=httpx.Response(200, json=empty_response)
        )

        ctx = make_ctx(client)
        result = await nhc_get_storm_watches_warnings(ctx, storm_id="AL052024")

        assert "No watches or warnings" in result
        assert "AL052024" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_watches_warnings_timeout(self, client):
        """A timeout on the ArcGIS call should produce a user-friendly message."""
        storms_fixture = load_json_fixture("active_storms_with_data.json")
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=storms_fixture)
        )

        respx.get(url__startswith=ARCGIS_BASE_URL).mock(
            side_effect=httpx.ReadTimeout("timeout")
        )

        ctx = make_ctx(client)
        result = await nhc_get_storm_watches_warnings(ctx, storm_id="AL052024")

        assert "timed out" in result


# ===========================================================================
# nhc_get_best_track
# ===========================================================================


class TestGetBestTrack:
    """Tests for the nhc_get_best_track tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_best_track_hurdat2_markdown(self, client):
        """Historical storm best track should use HURDAT2 and return markdown table."""
        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )

        ctx = make_ctx(client)
        result = await nhc_get_best_track(ctx, storm_id="AL011851")

        assert "Best Track" in result
        assert "AL011851" in result
        assert "HURDAT2" in result
        assert "| Date/Time |" in result
        assert "track points" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_best_track_hurdat2_json(self, client):
        """Historical storm best track JSON should contain track_points array."""
        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )

        ctx = make_ctx(client)
        result = await nhc_get_best_track(
            ctx, storm_id="AL011851", response_format="json"
        )

        data = json.loads(result)
        assert data["storm_id"] == "AL011851"
        assert data["source"] == "HURDAT2"
        assert data["count"] == len(data["track_points"])
        assert data["count"] == 14  # AL011851 has 14 entries in the fixture

    @respx.mock
    @pytest.mark.asyncio
    async def test_best_track_hurdat2_track_point_fields(self, client):
        """Each track point should include datetime, lat, lon, wind, pressure, status, category."""
        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )

        ctx = make_ctx(client)
        result = await nhc_get_best_track(
            ctx, storm_id="AL011851", response_format="json"
        )

        pt = json.loads(result)["track_points"][0]
        assert "datetime" in pt
        assert "lat" in pt
        assert "lon" in pt
        assert "max_wind" in pt
        assert "min_pressure" in pt
        assert "status" in pt
        assert "category" in pt

    @respx.mock
    @pytest.mark.asyncio
    async def test_best_track_hurdat2_wind_classification(self, client):
        """Track points should have correct Saffir-Simpson category from wind speed."""
        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )

        ctx = make_ctx(client)
        result = await nhc_get_best_track(
            ctx, storm_id="AL011851", response_format="json"
        )

        points = json.loads(result)["track_points"]
        # AL011851 first point has max_wind=80 -> Category 1
        assert points[0]["max_wind"] == 80
        assert points[0]["category"] == "Category 1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_best_track_atcf_for_recent_storm(self, client):
        """Recent storms should try ATCF B-deck first."""
        # Create a minimal ATCF B-deck fixture
        atcf_text = (
            "AL, 05, 2025090100,   , BEST,   0, 255N,  852W, 120,  950, HU,  34, NEQ, 120, 100, 80, 100,\n"
            "AL, 05, 2025090106,   , BEST,   0, 265N,  840W, 130,  940, HU,  34, NEQ, 120, 100, 80, 100,\n"
            "AL, 05, 2025090112,   , BEST,   0, 278N,  825W, 115,  955, HU,  34, NEQ, 120, 100, 80, 100,\n"
        )
        respx.get("https://ftp.nhc.noaa.gov/atcf/btk/bal052025.dat").mock(
            return_value=httpx.Response(200, text=atcf_text)
        )

        ctx = make_ctx(client)
        # Year 2025 is within current_year - 1, so ATCF is tried first
        result = await nhc_get_best_track(
            ctx, storm_id="AL052025", response_format="json"
        )

        data = json.loads(result)
        assert data["source"] == "ATCF B-deck"
        assert data["count"] == 3
        assert data["track_points"][0]["max_wind"] == 120

    @respx.mock
    @pytest.mark.asyncio
    async def test_best_track_atcf_fallback_to_hurdat2(self, client):
        """If ATCF 404s for a recent storm, it should fall back to HURDAT2."""
        # ATCF returns 404
        respx.get("https://ftp.nhc.noaa.gov/atcf/btk/bal012025.dat").mock(
            return_value=httpx.Response(404)
        )

        # HURDAT2 has the storm
        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )

        ctx = make_ctx(client)
        # AL012025 will not be found in the 1851 HURDAT2 fixture, so we get "not found"
        result = await nhc_get_best_track(ctx, storm_id="AL012025")

        # The ATCF failed and HURDAT2 doesn't have AL012025, so expect not-found
        assert "No best track data found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_best_track_storm_not_found(self, client):
        """A valid storm ID format but non-existent storm returns a not-found message."""
        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )

        ctx = make_ctx(client)
        result = await nhc_get_best_track(ctx, storm_id="AL991999")

        assert "No best track data found" in result
        assert "nhc_search_storms" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_best_track_invalid_storm_id(self, client):
        """An invalid storm ID format should return a validation error message."""
        ctx = make_ctx(client)
        result = await nhc_get_best_track(ctx, storm_id="INVALID")

        assert "Error" in result
        assert "Invalid storm ID" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_best_track_hurdat2_http_error(self, client):
        """An HTTP error from HURDAT2 should be caught and reported."""
        respx.get(HURDAT2_URLS["al"]).mock(return_value=httpx.Response(503))

        ctx = make_ctx(client)
        result = await nhc_get_best_track(ctx, storm_id="AL011851")

        assert "Error" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_best_track_multi_storm_hurdat2_selects_correct(self, client):
        """When HURDAT2 has multiple storms the tool should extract the correct one."""
        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )

        ctx = make_ctx(client)
        # AL041851 is the 4th storm in the fixture with 49 entries
        result = await nhc_get_best_track(
            ctx, storm_id="AL041851", response_format="json"
        )

        data = json.loads(result)
        assert data["storm_id"] == "AL041851"
        assert data["source"] == "HURDAT2"
        # The fixture has entries for AL041851 starting at line 20
        assert data["count"] > 0


# ===========================================================================
# nhc_search_storms
# ===========================================================================


class TestSearchStorms:
    """Tests for the nhc_search_storms tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_no_filters_returns_guidance(self, client):
        """Calling search with no filters should return usage guidance."""
        ctx = make_ctx(client)
        result = await nhc_search_storms(ctx)

        assert "Please provide at least one search filter" in result
        assert "name" in result
        assert "year" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_by_year_markdown(self, client):
        """Searching by year should return storms from that year as a markdown table."""
        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )
        respx.get(HURDAT2_URLS["ep"]).mock(return_value=httpx.Response(200, text=""))

        ctx = make_ctx(client)
        result = await nhc_search_storms(ctx, year=1851)

        assert "Storm Search Results" in result
        assert "| Storm ID |" in result
        assert "AL011851" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_by_year_json(self, client):
        """JSON search results should include storms array, total_matches, and showing."""
        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )
        respx.get(HURDAT2_URLS["ep"]).mock(return_value=httpx.Response(200, text=""))

        ctx = make_ctx(client)
        result = await nhc_search_storms(ctx, year=1851, response_format="json")

        data = json.loads(result)
        assert "storms" in data
        assert "total_matches" in data
        assert "showing" in data
        # The fixture has 4 storms from 1851
        assert data["total_matches"] == 4

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_by_year_storm_fields(self, client):
        """Each storm result should have id, name, year, basin, peak_wind, min_pressure, category."""
        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )
        respx.get(HURDAT2_URLS["ep"]).mock(return_value=httpx.Response(200, text=""))

        ctx = make_ctx(client)
        result = await nhc_search_storms(ctx, year=1851, response_format="json")

        storm = json.loads(result)["storms"][0]
        expected_keys = {
            "id",
            "name",
            "year",
            "basin",
            "peak_wind",
            "min_pressure",
            "category",
            "track_points",
        }
        assert expected_keys == set(storm.keys())

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_by_basin_atlantic_only(self, client):
        """Filtering by basin='al' should only search the Atlantic HURDAT2 file."""
        from nhc_mcp.models import Basin

        hurdat2_text = load_fixture("hurdat2_sample.txt")
        # Only AL route should be called
        al_route = respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )
        ep_route = respx.get(HURDAT2_URLS["ep"]).mock(
            return_value=httpx.Response(200, text="")
        )

        ctx = make_ctx(client)
        await nhc_search_storms(ctx, year=1851, basin=Basin.AL)

        assert al_route.called
        assert not ep_route.called

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_by_min_wind(self, client):
        """Filtering by min_wind should only return storms at or above that intensity."""
        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )
        respx.get(HURDAT2_URLS["ep"]).mock(return_value=httpx.Response(200, text=""))

        ctx = make_ctx(client)
        # Only AL041851 peaks at 100kt in the sample; AL011851 peaks at 80kt
        # AL021851 at 80kt; AL031851 at 50kt
        result = await nhc_search_storms(
            ctx, year=1851, min_wind=96, response_format="json"
        )

        data = json.loads(result)
        for storm in data["storms"]:
            assert isinstance(storm["peak_wind"], int)
            assert storm["peak_wind"] >= 96

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_no_results(self, client):
        """A search that matches no storms should return a no-results message."""
        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )
        respx.get(HURDAT2_URLS["ep"]).mock(return_value=httpx.Response(200, text=""))

        ctx = make_ctx(client)
        result = await nhc_search_storms(ctx, name="NONEXISTENT")

        assert "No storms found" in result
        assert "HURDAT2" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_limit(self, client):
        """The limit parameter should cap the number of returned results."""
        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )
        respx.get(HURDAT2_URLS["ep"]).mock(return_value=httpx.Response(200, text=""))

        ctx = make_ctx(client)
        result = await nhc_search_storms(
            ctx, year=1851, limit=2, response_format="json"
        )

        data = json.loads(result)
        assert data["showing"] == 2
        assert data["total_matches"] == 4  # 4 storms in 1851 in the fixture

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_results_sorted_by_year_desc(self, client):
        """Results should be sorted by year descending, then by peak wind descending."""
        # The fixture has storms from 1851 and 2005 (Katrina + Ida)
        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )
        respx.get(HURDAT2_URLS["ep"]).mock(return_value=httpx.Response(200, text=""))

        ctx = make_ctx(client)
        # Search for UNNAMED storms in 1851 — there are multiple
        result = await nhc_search_storms(ctx, name="UNNAMED", response_format="json")

        data = json.loads(result)
        storms = data["storms"]
        # All UNNAMED storms are from 1851, so check wind descending
        winds = []
        for s in storms:
            w = s["peak_wind"]
            winds.append(w if isinstance(w, int) else 0)
        assert winds == sorted(winds, reverse=True)

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_hurdat2_http_error(self, client):
        """An HTTP error fetching HURDAT2 should be caught and reported."""
        respx.get(HURDAT2_URLS["al"]).mock(return_value=httpx.Response(500))
        respx.get(HURDAT2_URLS["ep"]).mock(return_value=httpx.Response(200, text=""))

        ctx = make_ctx(client)
        result = await nhc_search_storms(ctx, year=1851)

        assert "Error" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_metadata_in_markdown(self, client):
        """Markdown output should include filter descriptions in metadata."""
        from nhc_mcp.models import Basin

        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )

        ctx = make_ctx(client)
        result = await nhc_search_storms(
            ctx, name="UNNAMED", year=1851, basin=Basin.AL, min_wind=64
        )

        assert "Name: UNNAMED" in result
        assert "Year: 1851" in result
        assert "Basin: AL" in result
        assert "Min wind: 64 kt" in result


# ===========================================================================
# Cross-cutting / edge-case tests
# ===========================================================================


class TestEdgeCases:
    """Additional edge-case and cross-cutting tests for tool functions."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_forecast_track_uses_correct_arcgis_layer(self, client):
        """The forecast track tool should query the correct ArcGIS layer for AT5."""
        storms_fixture = load_json_fixture("active_storms_with_data.json")
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=storms_fixture)
        )

        # AT5 forecast_points layer_id = 6 + 4*26 = 110
        forecast_fixture = load_json_fixture("forecast_track.json")
        arcgis_route = respx.get(url__startswith=ARCGIS_BASE_URL).mock(
            return_value=httpx.Response(200, json=forecast_fixture)
        )

        ctx = make_ctx(client)
        await nhc_get_forecast_track(ctx, storm_id="AL052024")

        assert arcgis_route.called
        called_url = str(arcgis_route.calls[0].request.url)
        # AT5 is slot index 4, forecast_points base is 6: 6 + 4*26 = 110
        assert "/110/query" in called_url

    @respx.mock
    @pytest.mark.asyncio
    async def test_watches_warnings_uses_correct_arcgis_layer(self, client):
        """The watches/warnings tool should query the correct ArcGIS layer for AT5."""
        storms_fixture = load_json_fixture("active_storms_with_data.json")
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=storms_fixture)
        )

        # AT5 watch_warning layer_id = 9 + 4*26 = 113
        ww_fixture = load_json_fixture("watches_warnings.json")
        arcgis_route = respx.get(url__startswith=ARCGIS_BASE_URL).mock(
            return_value=httpx.Response(200, json=ww_fixture)
        )

        ctx = make_ctx(client)
        await nhc_get_storm_watches_warnings(ctx, storm_id="AL052024")

        assert arcgis_route.called
        called_url = str(arcgis_route.calls[0].request.url)
        # AT5 is slot index 4, watch_warning base is 9: 9 + 4*26 = 113
        assert "/113/query" in called_url

    @respx.mock
    @pytest.mark.asyncio
    async def test_best_track_east_pacific_uses_ep_hurdat2(self, client):
        """An EP storm should fetch the East Pacific HURDAT2 file."""
        ep_route = respx.get(HURDAT2_URLS["ep"]).mock(
            return_value=httpx.Response(200, text="")
        )

        ctx = make_ctx(client)
        result = await nhc_get_best_track(ctx, storm_id="EP011949")

        assert ep_route.called
        assert "No best track data found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_active_storms_no_advisory_url_field(self, client):
        """Storms without a publicAdvisory field should still produce valid output."""
        fixture = {
            "activeStorms": [
                {
                    "id": "al012024",
                    "binNumber": "AT1",
                    "name": "TestStorm",
                    "classification": "TS",
                }
            ]
        }
        respx.get(CURRENT_STORMS_URL).mock(
            return_value=httpx.Response(200, json=fixture)
        )

        ctx = make_ctx(client)
        result = await nhc_get_active_storms(ctx, response_format="json")

        data = json.loads(result)
        assert data["count"] == 1
        assert data["active_storms"][0]["advisory_url"] == ""

    @respx.mock
    @pytest.mark.asyncio
    async def test_best_track_hurdat2_negative_pressure_treated_as_none(self, client):
        """HURDAT2 entries with -999 pressure should parse as None."""
        hurdat2_text = load_fixture("hurdat2_sample.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=hurdat2_text)
        )

        ctx = make_ctx(client)
        result = await nhc_get_best_track(
            ctx, storm_id="AL011851", response_format="json"
        )

        data = json.loads(result)
        # AL011851 in the fixture has all min_pressure values as -999
        for pt in data["track_points"]:
            assert pt["min_pressure"] is None

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_storms_katrina(self, client):
        """Searching for KATRINA should find it in the HURDAT2 data."""
        # Use the best_track.txt fixture which contains Katrina in HURDAT2 format
        katrina_hurdat2 = load_fixture("best_track.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=katrina_hurdat2)
        )
        respx.get(HURDAT2_URLS["ep"]).mock(return_value=httpx.Response(200, text=""))

        ctx = make_ctx(client)
        result = await nhc_search_storms(ctx, name="KATRINA", response_format="json")

        data = json.loads(result)
        assert data["total_matches"] == 1
        storm = data["storms"][0]
        assert storm["id"] == "AL092005"
        assert storm["name"] == "KATRINA"
        assert storm["peak_wind"] == 80  # Max wind in the best_track.txt fixture
        assert storm["category"] == "Category 1"

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_storms_case_insensitive(self, client):
        """Storm name search should be case-insensitive."""
        katrina_hurdat2 = load_fixture("best_track.txt")
        respx.get(HURDAT2_URLS["al"]).mock(
            return_value=httpx.Response(200, text=katrina_hurdat2)
        )
        respx.get(HURDAT2_URLS["ep"]).mock(return_value=httpx.Response(200, text=""))

        ctx = make_ctx(client)
        result = await nhc_search_storms(ctx, name="katrina", response_format="json")

        data = json.loads(result)
        assert data["total_matches"] == 1
        assert data["storms"][0]["name"] == "KATRINA"
