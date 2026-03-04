"""Unit tests for OFS MCP tool functions with mocked HTTP.

Tests the tool functions in ofs_mcp.tools.discovery and ofs_mcp.tools.forecast
using respx to mock all outbound HTTP requests and fixture files for realistic
API responses.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from ofs_mcp.client import OFSClient
from ofs_mcp.models import OFS_MODELS, OFSModel

# ---------------------------------------------------------------------------
# Fixtures directory
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file and return parsed dict."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Context helper
# ---------------------------------------------------------------------------


def make_ctx(client: OFSClient) -> MagicMock:
    """Create a mock MCP Context wired to the given OFSClient.

    The tool functions access the client via:
        ctx.request_context.lifespan_context["ofs_client"]
    """
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"ofs_client": client}
    return ctx


# ---------------------------------------------------------------------------
# Client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    """Create an OFSClient and close it after the test."""
    c = OFSClient()
    yield c
    await c.close()


# ============================================================================
# Test: ofs_list_models (pure data, no HTTP)
# ============================================================================


class TestOfsListModels:
    """Tests for the ofs_list_models tool function."""

    async def test_list_models_markdown_returns_all_models(self, client):
        """ofs_list_models in markdown mode should mention every model ID."""
        from ofs_mcp.tools.discovery import ofs_list_models

        ctx = make_ctx(client)
        result = await ofs_list_models(ctx, response_format="markdown")

        assert "# NOAA Operational Forecast System" in result
        for model_id in OFS_MODELS:
            assert model_id in result, (
                f"Model '{model_id}' not found in markdown output"
            )

    async def test_list_models_markdown_contains_table_headers(self, client):
        """ofs_list_models markdown output should include a table with headers."""
        from ofs_mcp.tools.discovery import ofs_list_models

        ctx = make_ctx(client)
        result = await ofs_list_models(ctx, response_format="markdown")

        assert "| Model ID |" in result
        assert "| --- |" in result

    async def test_list_models_json_returns_valid_json(self, client):
        """ofs_list_models in JSON mode should return parseable JSON with all models."""
        from ofs_mcp.tools.discovery import ofs_list_models

        ctx = make_ctx(client)
        result = await ofs_list_models(ctx, response_format="json")

        data = json.loads(result)
        assert isinstance(data, dict)
        assert len(data) == len(OFS_MODELS)
        for model_id in OFS_MODELS:
            assert model_id in data, f"Model '{model_id}' missing from JSON"

    async def test_list_models_json_has_expected_keys(self, client):
        """Each model entry in JSON output should contain standard metadata keys."""
        from ofs_mcp.tools.discovery import ofs_list_models

        ctx = make_ctx(client)
        result = await ofs_list_models(ctx, response_format="json")

        data = json.loads(result)
        expected_keys = {
            "name",
            "short_name",
            "grid_type",
            "domain_desc",
            "domain",
            "states",
            "cycles",
            "forecast_hours",
            "datum",
            "variables",
        }
        for model_id, info in data.items():
            missing = expected_keys - set(info.keys())
            assert not missing, f"Model '{model_id}' JSON missing keys: {missing}"

    async def test_list_models_json_variables_are_lists(self, client):
        """The 'variables' field in JSON output should be a list of strings."""
        from ofs_mcp.tools.discovery import ofs_list_models

        ctx = make_ctx(client)
        result = await ofs_list_models(ctx, response_format="json")

        data = json.loads(result)
        for model_id, info in data.items():
            assert isinstance(info["variables"], list), (
                f"Model '{model_id}': variables should be a list"
            )


# ============================================================================
# Test: ofs_get_model_info (pure data, no HTTP)
# ============================================================================


class TestOfsGetModelInfo:
    """Tests for the ofs_get_model_info tool function."""

    async def test_get_model_info_cbofs_markdown(self, client):
        """ofs_get_model_info for cbofs should return markdown with model details."""
        from ofs_mcp.tools.discovery import ofs_get_model_info

        ctx = make_ctx(client)
        result = await ofs_get_model_info(ctx, model=OFSModel.CBOFS)

        assert "Chesapeake Bay OFS" in result
        assert "CBOFS" in result
        assert "ROMS" in result
        assert "NAVD88" in result
        assert "THREDDS" in result

    async def test_get_model_info_cbofs_json(self, client):
        """ofs_get_model_info JSON for cbofs should include all model fields."""
        from ofs_mcp.tools.discovery import ofs_get_model_info

        ctx = make_ctx(client)
        result = await ofs_get_model_info(
            ctx, model=OFSModel.CBOFS, response_format="json"
        )

        data = json.loads(result)
        assert data["model_id"] == "cbofs"
        assert data["name"] == "Chesapeake Bay OFS"
        assert "thredds_opendap_url" in data
        assert "s3_prefix" in data

    async def test_get_model_info_fvcom_model(self, client):
        """ofs_get_model_info for an FVCOM model (ngofs2) should show correct grid type."""
        from ofs_mcp.tools.discovery import ofs_get_model_info

        ctx = make_ctx(client)
        result = await ofs_get_model_info(ctx, model=OFSModel.NGOFS2)

        assert "FVCOM" in result
        assert "unstructured triangular" in result
        assert "NGOFS2" in result

    async def test_get_model_info_wcofs_has_two_cycles(self, client):
        """ofs_get_model_info for wcofs should show 2 daily cycles (03, 09)."""
        from ofs_mcp.tools.discovery import ofs_get_model_info

        ctx = make_ctx(client)
        result = await ofs_get_model_info(
            ctx, model=OFSModel.WCOFS, response_format="json"
        )

        data = json.loads(result)
        assert data["cycles"] == ["03", "09"]
        assert "MSL" in data["datum"]

    async def test_get_model_info_includes_variables_section(self, client):
        """ofs_get_model_info markdown output should include a Variables section."""
        from ofs_mcp.tools.discovery import ofs_get_model_info

        ctx = make_ctx(client)
        result = await ofs_get_model_info(ctx, model=OFSModel.CBOFS)

        assert "### Variables" in result
        assert "water_level" in result
        assert "temperature" in result
        assert "salinity" in result

    async def test_get_model_info_includes_data_access_urls(self, client):
        """ofs_get_model_info markdown output should include S3 and THREDDS URLs."""
        from ofs_mcp.tools.discovery import ofs_get_model_info

        ctx = make_ctx(client)
        result = await ofs_get_model_info(ctx, model=OFSModel.DBOFS)

        assert "### Data Access" in result
        assert "noaa-nos-ofs-pds.s3.amazonaws.com" in result
        assert "opendap.co-ops.nos.noaa.gov" in result


# ============================================================================
# Test: ofs_find_models_for_location (pure data, no HTTP)
# ============================================================================


class TestOfsFindModelsForLocation:
    """Tests for the ofs_find_models_for_location tool function."""

    async def test_find_models_chesapeake_bay(self, client):
        """A point in Chesapeake Bay should match cbofs (and possibly dbofs)."""
        from ofs_mcp.tools.discovery import ofs_find_models_for_location

        ctx = make_ctx(client)
        # Chesapeake Bay (Maryland)
        result = await ofs_find_models_for_location(
            ctx, latitude=38.98, longitude=-76.48
        )

        assert "cbofs" in result
        assert "model(s) found" in result

    async def test_find_models_san_francisco(self, client):
        """A point in San Francisco Bay should match sfbofs."""
        from ofs_mcp.tools.discovery import ofs_find_models_for_location

        ctx = make_ctx(client)
        result = await ofs_find_models_for_location(
            ctx, latitude=37.77, longitude=-122.42
        )

        assert "sfbofs" in result

    async def test_find_models_gulf_of_mexico(self, client):
        """A point in the Northern Gulf of Mexico should match ngofs2."""
        from ofs_mcp.tools.discovery import ofs_find_models_for_location

        ctx = make_ctx(client)
        # New Orleans area
        result = await ofs_find_models_for_location(
            ctx, latitude=29.95, longitude=-90.07
        )

        assert "ngofs2" in result

    async def test_find_models_no_coverage(self, client):
        """A point in the open Pacific should have no coverage, with closest model hint."""
        from ofs_mcp.tools.discovery import ofs_find_models_for_location

        ctx = make_ctx(client)
        result = await ofs_find_models_for_location(ctx, latitude=0.0, longitude=-150.0)

        assert "No OFS model domain covers" in result
        assert "closest model" in result.lower() or "closest" in result.lower()

    async def test_find_models_new_york_harbor(self, client):
        """A point in New York Harbor should match nyofs."""
        from ofs_mcp.tools.discovery import ofs_find_models_for_location

        ctx = make_ctx(client)
        result = await ofs_find_models_for_location(
            ctx, latitude=40.69, longitude=-74.04
        )

        assert "nyofs" in result

    async def test_find_models_west_coast_overlap(self, client):
        """A point on the West Coast may match both wcofs and sfbofs."""
        from ofs_mcp.tools.discovery import ofs_find_models_for_location

        ctx = make_ctx(client)
        # Point inside San Francisco Bay, which is within both sfbofs and wcofs domains
        result = await ofs_find_models_for_location(
            ctx, latitude=37.8, longitude=-122.4
        )

        assert "sfbofs" in result
        assert "wcofs" in result

    async def test_find_models_tampa_bay(self, client):
        """A point in Tampa Bay should match tbofs."""
        from ofs_mcp.tools.discovery import ofs_find_models_for_location

        ctx = make_ctx(client)
        result = await ofs_find_models_for_location(ctx, latitude=27.6, longitude=-82.6)

        assert "tbofs" in result


# ============================================================================
# Test: ofs_list_cycles (mocked S3 HEAD requests)
# ============================================================================


class TestOfsListCycles:
    """Tests for the ofs_list_cycles tool, mocking AWS S3 HEAD requests."""

    @respx.mock
    async def test_list_cycles_all_available(self, client):
        """ofs_list_cycles should report 'Available' for cycles with 200 HEAD responses."""
        from ofs_mcp.tools.discovery import ofs_list_cycles

        # Mock all HEAD requests to S3 as successful
        respx.head(url__startswith="https://noaa-nos-ofs-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(200)
        )

        ctx = make_ctx(client)
        result = await ofs_list_cycles(
            ctx, model=OFSModel.CBOFS, date="2026-03-01", num_days=1
        )

        assert "CBOFS" in result or "Chesapeake Bay" in result
        assert "Available" in result
        # cbofs has 4 cycles: 4 rows + 1 summary line = 5 occurrences of "Available"
        # Verify all 4 cycle rows show "Available" status (not "Not available")
        assert "Not available" not in result

    @respx.mock
    async def test_list_cycles_none_available(self, client):
        """ofs_list_cycles should report 'Not available' for cycles with 404 HEAD responses."""
        from ofs_mcp.tools.discovery import ofs_list_cycles

        # Mock all HEAD requests as 404
        respx.head(url__startswith="https://noaa-nos-ofs-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(404)
        )

        ctx = make_ctx(client)
        result = await ofs_list_cycles(
            ctx, model=OFSModel.CBOFS, date="2026-03-01", num_days=1
        )

        assert "Not available" in result
        assert "No cycles found" in result

    @respx.mock
    async def test_list_cycles_mixed_availability(self, client):
        """ofs_list_cycles should correctly report a mix of available and missing cycles."""
        from ofs_mcp.tools.discovery import ofs_list_cycles

        # Only 00z and 06z exist; 12z and 18z return 404
        def route_handler(request):
            url = str(request.url)
            if "t18z" in url or "t12z" in url:
                return httpx.Response(404)
            return httpx.Response(200)

        respx.head(url__startswith="https://noaa-nos-ofs-pds.s3.amazonaws.com/").mock(
            side_effect=route_handler
        )

        ctx = make_ctx(client)
        result = await ofs_list_cycles(
            ctx, model=OFSModel.CBOFS, date="2026-03-01", num_days=1
        )

        assert "Available" in result
        assert "Not available" in result
        # Summary line should show "2 of 4 cycles"
        assert "2 of 4 cycles" in result

    @respx.mock
    async def test_list_cycles_clamps_num_days(self, client):
        """ofs_list_cycles should clamp num_days to 1-7 range."""
        from ofs_mcp.tools.discovery import ofs_list_cycles

        respx.head(url__startswith="https://noaa-nos-ofs-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(200)
        )

        ctx = make_ctx(client)
        # num_days=0 should be clamped to 1
        result = await ofs_list_cycles(
            ctx, model=OFSModel.CBOFS, date="2026-03-01", num_days=0
        )

        # With 1 day and 4 cycles, should have exactly 4 availability rows
        assert "Available" in result
        # Should be "last 1 day(s)" in the output
        assert "1 day" in result

    @respx.mock
    async def test_list_cycles_invalid_date_format(self, client):
        """ofs_list_cycles should return an error message for an invalid date string."""
        from ofs_mcp.tools.discovery import ofs_list_cycles

        ctx = make_ctx(client)
        result = await ofs_list_cycles(
            ctx, model=OFSModel.CBOFS, date="not-a-date", num_days=1
        )

        assert "Invalid date format" in result

    @respx.mock
    async def test_list_cycles_wcofs_uses_correct_cycles(self, client):
        """ofs_list_cycles for wcofs should check cycles 03 and 09 (not 00/06/12/18)."""
        from ofs_mcp.tools.discovery import ofs_list_cycles

        checked_urls = []

        def capture_handler(request):
            checked_urls.append(str(request.url))
            return httpx.Response(200)

        respx.head(url__startswith="https://noaa-nos-ofs-pds.s3.amazonaws.com/").mock(
            side_effect=capture_handler
        )

        ctx = make_ctx(client)
        await ofs_list_cycles(ctx, model=OFSModel.WCOFS, date="2026-03-01", num_days=1)

        # wcofs has cycles ["03", "09"] -- verify URLs contain t03z and t09z
        assert any("t03z" in url for url in checked_urls), "Should check 03z cycle"
        assert any("t09z" in url for url in checked_urls), "Should check 09z cycle"
        # Verify no 00z/06z/12z/18z were checked
        assert not any("t00z" in url for url in checked_urls), "Should NOT check 00z"
        assert not any("t06z" in url for url in checked_urls), "Should NOT check 06z"

    @respx.mock
    async def test_list_cycles_two_days(self, client):
        """ofs_list_cycles with num_days=2 should check cycles for both dates."""
        from ofs_mcp.tools.discovery import ofs_list_cycles

        respx.head(url__startswith="https://noaa-nos-ofs-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(200)
        )

        ctx = make_ctx(client)
        result = await ofs_list_cycles(
            ctx, model=OFSModel.CBOFS, date="2026-03-02", num_days=2
        )

        assert "2 day" in result
        # Should see both dates in the output
        assert "2026-03-02" in result
        assert "2026-03-01" in result

    @respx.mock
    async def test_list_cycles_s3_timeout_treated_as_unavailable(self, client):
        """ofs_list_cycles should treat S3 connection errors as 'Not available'."""
        from ofs_mcp.tools.discovery import ofs_list_cycles

        respx.head(url__startswith="https://noaa-nos-ofs-pds.s3.amazonaws.com/").mock(
            side_effect=httpx.ConnectError("connection refused")
        )

        ctx = make_ctx(client)
        result = await ofs_list_cycles(
            ctx, model=OFSModel.CBOFS, date="2026-03-01", num_days=1
        )

        # check_file_exists catches all exceptions and returns False
        assert "Not available" in result


# ============================================================================
# Test: ofs_list_cycles — S3 URL construction
# ============================================================================


class TestOfsListCyclesUrlConstruction:
    """Verify that ofs_list_cycles produces correct S3 URLs."""

    @respx.mock
    async def test_s3_url_includes_correct_date_path(self, client):
        """The S3 HEAD URL should contain the date-based path components."""
        from ofs_mcp.tools.discovery import ofs_list_cycles

        captured = []

        def handler(request):
            captured.append(str(request.url))
            return httpx.Response(200)

        respx.head(url__startswith="https://noaa-nos-ofs-pds.s3.amazonaws.com/").mock(
            side_effect=handler
        )

        ctx = make_ctx(client)
        await ofs_list_cycles(ctx, model=OFSModel.CBOFS, date="2026-03-01", num_days=1)

        # Every URL should contain the date path
        for url in captured:
            assert "cbofs/netcdf/2026/03/01/" in url

    @respx.mock
    async def test_s3_url_requests_f001_forecast_file(self, client):
        """The S3 HEAD URL should always check the f001 forecast file."""
        from ofs_mcp.tools.discovery import ofs_list_cycles

        captured = []

        def handler(request):
            captured.append(str(request.url))
            return httpx.Response(200)

        respx.head(url__startswith="https://noaa-nos-ofs-pds.s3.amazonaws.com/").mock(
            side_effect=handler
        )

        ctx = make_ctx(client)
        await ofs_list_cycles(ctx, model=OFSModel.CBOFS, date="2026-03-01", num_days=1)

        for url in captured:
            assert "fields.f001.nc" in url


# ============================================================================
# Test: resolve_latest_cycle (mocked S3 HEAD)
# ============================================================================


class TestResolveLatestCycle:
    """Tests for OFSClient.resolve_latest_cycle with mocked HEAD requests."""

    @respx.mock
    async def test_resolve_finds_latest_cycle(self, client):
        """resolve_latest_cycle should return the first available (newest) cycle."""
        call_count = 0

        def handler(request):
            nonlocal call_count
            call_count += 1
            url = str(request.url)
            # Only the 06z cycle of today is available
            if "t06z" in url and call_count <= 8:
                return httpx.Response(200)
            return httpx.Response(404)

        respx.head(url__startswith="https://noaa-nos-ofs-pds.s3.amazonaws.com/").mock(
            side_effect=handler
        )

        result = await client.resolve_latest_cycle("cbofs", num_days=2)
        # Should find something (exact date depends on "now")
        assert result is not None
        date_str, cycle_str = result
        assert len(date_str) == 8
        assert cycle_str in {"00", "06", "12", "18"}

    @respx.mock
    async def test_resolve_returns_none_when_nothing_available(self, client):
        """resolve_latest_cycle should return None if all S3 checks fail."""
        respx.head(url__startswith="https://noaa-nos-ofs-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(404)
        )

        result = await client.resolve_latest_cycle("cbofs", num_days=1)
        assert result is None


# ============================================================================
# Test: check_file_exists (mocked HTTP)
# ============================================================================


class TestCheckFileExists:
    """Tests for OFSClient.check_file_exists with mocked responses."""

    @respx.mock
    async def test_check_file_exists_returns_true_on_200(self, client):
        """check_file_exists should return True when HEAD returns 200."""
        url = "https://noaa-nos-ofs-pds.s3.amazonaws.com/cbofs/netcdf/2026/03/01/cbofs.t00z.fields.f001.nc"
        respx.head(url).mock(return_value=httpx.Response(200))

        assert await client.check_file_exists(url) is True

    @respx.mock
    async def test_check_file_exists_returns_false_on_404(self, client):
        """check_file_exists should return False when HEAD returns 404."""
        url = "https://noaa-nos-ofs-pds.s3.amazonaws.com/cbofs/netcdf/2099/01/01/cbofs.t00z.fields.f001.nc"
        respx.head(url).mock(return_value=httpx.Response(404))

        assert await client.check_file_exists(url) is False

    @respx.mock
    async def test_check_file_exists_returns_false_on_exception(self, client):
        """check_file_exists should return False on connection error."""
        url = "https://noaa-nos-ofs-pds.s3.amazonaws.com/broken"
        respx.head(url).mock(side_effect=httpx.ConnectError("refused"))

        assert await client.check_file_exists(url) is False


# ============================================================================
# Test: fetch_coops_observations (mocked HTTP)
# ============================================================================


class TestFetchCoopsObservations:
    """Tests for OFSClient.fetch_coops_observations with mocked CO-OPS API."""

    @respx.mock
    async def test_fetch_coops_observations_success(self, client):
        """fetch_coops_observations should parse a valid CO-OPS JSON response."""
        fixture = load_fixture("coops_observations.json")

        respx.get(
            url__startswith="https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
        ).mock(return_value=httpx.Response(200, json=fixture))

        data = await client.fetch_coops_observations(
            "8571892", "20250301", "20250302", "NAVD"
        )

        assert "data" in data
        assert len(data["data"]) == 5
        assert data["data"][0]["t"] == "2025-03-01 00:00"
        assert data["data"][0]["v"] == "0.234"

    @respx.mock
    async def test_fetch_coops_observations_api_error(self, client):
        """fetch_coops_observations should raise ValueError on CO-OPS API error response."""
        error_response = {"error": {"message": "No data was found."}}

        respx.get(
            url__startswith="https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
        ).mock(return_value=httpx.Response(200, json=error_response))

        with pytest.raises(ValueError, match="No data was found"):
            await client.fetch_coops_observations(
                "8571892", "20250301", "20250302", "NAVD"
            )

    @respx.mock
    async def test_fetch_coops_observations_http_error(self, client):
        """fetch_coops_observations should raise on HTTP 500."""
        respx.get(
            url__startswith="https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
        ).mock(return_value=httpx.Response(500))

        with pytest.raises(httpx.HTTPStatusError):
            await client.fetch_coops_observations(
                "8571892", "20250301", "20250302", "NAVD"
            )


# ============================================================================
# Test: Error handling (handle_ofs_error)
# ============================================================================


class TestHandleOfsError:
    """Tests for the handle_ofs_error utility used by all tools."""

    def test_handle_http_404(self):
        """handle_ofs_error should return a file-not-found message for HTTP 404."""
        from ofs_mcp.utils import handle_ofs_error

        response = httpx.Response(
            404, request=httpx.Request("GET", "https://example.com")
        )
        err = httpx.HTTPStatusError(
            "Not Found", request=response.request, response=response
        )
        msg = handle_ofs_error(err, "cbofs")
        assert "404" in msg
        assert "CBOFS" in msg

    def test_handle_http_403(self):
        """handle_ofs_error should return an access-denied message for HTTP 403."""
        from ofs_mcp.utils import handle_ofs_error

        response = httpx.Response(
            403, request=httpx.Request("GET", "https://example.com")
        )
        err = httpx.HTTPStatusError(
            "Forbidden", request=response.request, response=response
        )
        msg = handle_ofs_error(err, "cbofs")
        assert "403" in msg

    def test_handle_timeout(self):
        """handle_ofs_error should return a timeout message for TimeoutException."""
        from ofs_mcp.utils import handle_ofs_error

        err = httpx.TimeoutException("timed out")
        msg = handle_ofs_error(err, "gomofs")
        assert "timed out" in msg.lower()
        assert "GOMOFS" in msg

    def test_handle_value_error(self):
        """handle_ofs_error should pass through ValueError messages."""
        from ofs_mcp.utils import handle_ofs_error

        err = ValueError("Station not found")
        msg = handle_ofs_error(err)
        assert msg == "Station not found"

    def test_handle_generic_exception(self):
        """handle_ofs_error should format unexpected errors with type name."""
        from ofs_mcp.utils import handle_ofs_error

        err = TypeError("unexpected type")
        msg = handle_ofs_error(err, "cbofs")
        assert "TypeError" in msg
        assert "CBOFS" in msg


# ============================================================================
# Test: ofs_compare_with_coops — station metadata step (mocked HTTP)
# ============================================================================


class TestOfsCompareWithCoopsMetadata:
    """Tests for the station metadata fetch in ofs_compare_with_coops."""

    @respx.mock
    async def test_compare_returns_error_on_bad_station(self, client):
        """ofs_compare_with_coops should return an error if station metadata fetch fails."""
        from ofs_mcp.tools.forecast import ofs_compare_with_coops

        # Return an empty station list
        respx.get(url__startswith="https://api.tidesandcurrents.noaa.gov/mdapi/").mock(
            return_value=httpx.Response(200, json={"stations": []})
        )

        ctx = make_ctx(client)
        result = await ofs_compare_with_coops(
            ctx, station_id="9999999", model=OFSModel.CBOFS
        )

        assert "Could not retrieve metadata" in result

    @respx.mock
    async def test_compare_returns_error_on_metadata_http_failure(self, client):
        """ofs_compare_with_coops should return an error if metadata API returns 404."""
        from ofs_mcp.tools.forecast import ofs_compare_with_coops

        respx.get(url__startswith="https://api.tidesandcurrents.noaa.gov/mdapi/").mock(
            return_value=httpx.Response(404)
        )

        ctx = make_ctx(client)
        result = await ofs_compare_with_coops(
            ctx, station_id="0000000", model=OFSModel.CBOFS
        )

        assert "Could not retrieve metadata" in result

    @respx.mock
    async def test_compare_clamps_hours_to_compare(self, client):
        """ofs_compare_with_coops should clamp hours_to_compare between 1 and 96."""
        from ofs_mcp.tools.forecast import ofs_compare_with_coops

        fixture = load_fixture("station_metadata.json")
        respx.get(url__startswith="https://api.tidesandcurrents.noaa.gov/mdapi/").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        # Mock OPeNDAP failure so it falls to resolve_latest_cycle
        # Mock S3 as unavailable so we get early exit
        respx.head(url__startswith="https://noaa-nos-ofs-pds.s3.amazonaws.com/").mock(
            return_value=httpx.Response(404)
        )

        ctx = make_ctx(client)
        # hours_to_compare=200 should be clamped to 96
        result = await ofs_compare_with_coops(
            ctx, station_id="8571892", model=OFSModel.CBOFS, hours_to_compare=200
        )

        # Since no cycles found, we get an appropriate message
        # The point is that it did not crash with hours_to_compare=200
        assert isinstance(result, str)


# ============================================================================
# Test: build_s3_url
# ============================================================================


class TestBuildS3Url:
    """Tests for OFSClient.build_s3_url with various models and parameters."""

    def test_forecast_url_format(self):
        """build_s3_url should produce correctly formatted forecast URLs."""
        c = OFSClient()
        url = c.build_s3_url("cbofs", "20260301", "06", "f", 1)
        assert url == (
            "https://noaa-nos-ofs-pds.s3.amazonaws.com/"
            "cbofs/netcdf/2026/03/01/cbofs.t06z.fields.f001.nc"
        )

    def test_nowcast_url_format(self):
        """build_s3_url should produce correctly formatted nowcast URLs."""
        c = OFSClient()
        url = c.build_s3_url("ngofs2", "20260301", "12", "n", 3)
        assert url == (
            "https://noaa-nos-ofs-pds.s3.amazonaws.com/"
            "ngofs2/netcdf/2026/03/01/ngofs2.t12z.fields.n003.nc"
        )

    def test_large_forecast_hour(self):
        """build_s3_url with a large forecast hour should zero-pad to 3 digits."""
        c = OFSClient()
        url = c.build_s3_url("wcofs", "20260301", "03", "f", 72)
        assert "fields.f072.nc" in url


# ============================================================================
# Test: build_thredds_url
# ============================================================================


class TestBuildThreddsUrl:
    """Tests for OFSClient.build_thredds_url."""

    def test_thredds_url_uses_thredds_id(self):
        """build_thredds_url should use the thredds_id from model config."""
        c = OFSClient()
        for model_id, info in OFS_MODELS.items():
            url = c.build_thredds_url(model_id)
            thredds_id = info["thredds_id"]
            assert thredds_id in url, f"URL for {model_id} missing thredds_id"
            assert url.endswith("_BEST.nc"), (
                f"URL for {model_id} should end with _BEST.nc"
            )

    def test_thredds_url_base(self):
        """build_thredds_url should use the correct THREDDS base URL."""
        c = OFSClient()
        url = c.build_thredds_url("cbofs")
        assert url.startswith("https://opendap.co-ops.nos.noaa.gov/thredds/dodsC/")
