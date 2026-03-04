"""Unit tests for erddap-mcp tool functions with mocked HTTP via respx.

Tests cover: erddap_search_datasets, erddap_get_dataset_info,
erddap_list_servers, erddap_get_all_datasets, erddap_get_griddap_data,
and erddap_get_tabledap_data.  Every HTTP call is intercepted by respx
so no network traffic occurs.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from erddap_mcp.client import ERDDAPClient

# ---------------------------------------------------------------------------
# Tool function imports
# ---------------------------------------------------------------------------
from erddap_mcp.tools.search import (
    erddap_get_all_datasets,
    erddap_list_servers,
    erddap_search_datasets,
)
from erddap_mcp.tools.metadata import erddap_get_dataset_info
from erddap_mcp.tools.griddap import erddap_get_griddap_data
from erddap_mcp.tools.tabledap import erddap_get_tabledap_data

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------
FIXTURES_DIR = Path(__file__).parent / "fixtures"
COASTWATCH = "https://coastwatch.pfeg.noaa.gov/erddap"


def _load_fixture(name: str) -> dict:
    """Load a JSON fixture file and return the parsed dict."""
    return json.loads((FIXTURES_DIR / name).read_text())


def make_ctx(client: ERDDAPClient) -> MagicMock:
    """Build a mock MCP Context whose lifespan_context holds *client*."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"erddap_client": client}
    return ctx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def erddap_client() -> ERDDAPClient:
    """Return a fresh ERDDAPClient (no teardown needed -- respx intercepts all IO)."""
    return ERDDAPClient()


@pytest.fixture()
def ctx(erddap_client: ERDDAPClient) -> MagicMock:
    """Return a mock MCP Context wired to *erddap_client*."""
    return make_ctx(erddap_client)


@pytest.fixture()
def search_fixture() -> dict:
    """Load the search_results.json fixture."""
    return _load_fixture("search_results.json")


@pytest.fixture()
def info_fixture() -> dict:
    """Load the dataset_info.json fixture."""
    return _load_fixture("dataset_info.json")


@pytest.fixture()
def all_datasets_fixture() -> dict:
    """Load the all_datasets.json fixture."""
    return _load_fixture("all_datasets.json")


@pytest.fixture()
def griddap_fixture() -> dict:
    """Load the griddap_data.json fixture."""
    return _load_fixture("griddap_data.json")


@pytest.fixture()
def tabledap_fixture() -> dict:
    """Load the tabledap_data.json fixture."""
    return _load_fixture("tabledap_data.json")


# =========================================================================
# erddap_list_servers
# =========================================================================
class TestListServers:
    """Tests for the erddap_list_servers tool."""

    @pytest.mark.asyncio
    async def test_list_all_servers(self, ctx: MagicMock) -> None:
        """Listing servers without filters returns a non-empty markdown table."""
        result = await erddap_list_servers(ctx)

        assert "## Known ERDDAP Servers" in result
        assert "CoastWatch West Coast" in result
        assert "servers listed" in result

    @pytest.mark.asyncio
    async def test_list_servers_filter_by_region(self, ctx: MagicMock) -> None:
        """Filtering servers by region returns only matching entries."""
        result = await erddap_list_servers(ctx, region="Global")

        assert "## Known ERDDAP Servers" in result
        assert "Region: Global" in result
        # Every row should be a Global server
        for line in result.split("\n"):
            if line.startswith("| ") and "Name" not in line and "---" not in line:
                assert "Global" in line

    @pytest.mark.asyncio
    async def test_list_servers_filter_by_keyword(self, ctx: MagicMock) -> None:
        """Filtering servers by keyword narrows results correctly."""
        result = await erddap_list_servers(ctx, keyword="glider")

        assert "Keyword: glider" in result
        assert "IOOS Gliders" in result

    @pytest.mark.asyncio
    async def test_list_servers_no_match(self, ctx: MagicMock) -> None:
        """A keyword with no match returns a helpful message."""
        result = await erddap_list_servers(ctx, keyword="zzz_nonexistent_zzz")

        assert "No ERDDAP servers match" in result


# =========================================================================
# erddap_search_datasets
# =========================================================================
class TestSearchDatasets:
    """Tests for the erddap_search_datasets tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_returns_markdown_table(
        self, ctx: MagicMock, search_fixture: dict
    ) -> None:
        """A successful search returns a markdown table of dataset results."""
        respx.get(url__startswith=f"{COASTWATCH}/search/index.json").mock(
            return_value=httpx.Response(200, json=search_fixture)
        )

        result = await erddap_search_datasets(ctx, search_for="sea surface temperature")

        assert "## Dataset Search Results" in result
        assert "goes_west" in result
        assert "datasets found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_filter_by_protocol(
        self, ctx: MagicMock, search_fixture: dict
    ) -> None:
        """Filtering search results by protocol='griddap' excludes tabledap-only rows."""
        respx.get(url__startswith=f"{COASTWATCH}/search/index.json").mock(
            return_value=httpx.Response(200, json=search_fixture)
        )

        result = await erddap_search_datasets(
            ctx, search_for="sea surface temperature", protocol="griddap"
        )

        assert "## Dataset Search Results" in result
        # All fixture rows happen to be griddap, so they should remain
        assert "goes_west" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_empty_results(self, ctx: MagicMock) -> None:
        """An empty result set returns a helpful no-data message."""
        empty = {"table": {"columnNames": ["Dataset ID"], "rows": []}}
        respx.get(url__startswith=f"{COASTWATCH}/search/index.json").mock(
            return_value=httpx.Response(200, json=empty)
        )

        result = await erddap_search_datasets(ctx, search_for="xyznonexistent")

        assert "No datasets found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_custom_server(
        self, ctx: MagicMock, search_fixture: dict
    ) -> None:
        """Search uses the provided server_url, not the default."""
        custom_url = "https://custom.example.com/erddap"
        respx.get(url__startswith=f"{custom_url}/search/index.json").mock(
            return_value=httpx.Response(200, json=search_fixture)
        )

        result = await erddap_search_datasets(
            ctx, search_for="sst", server_url=custom_url
        )

        assert custom_url in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_pagination_hint(self, ctx: MagicMock) -> None:
        """When result count equals items_per_page, the output hints at more pages."""
        # Build a fixture whose row count equals the requested items_per_page (2)
        rows = [
            [
                "https://example.com/griddap/a",
                "",
                "",
                "",
                "",
                "",
                "public",
                "Dataset A",
                "desc",
                "",
                "",
                "",
                "",
                "",
                "",
                "Inst",
                "dsA",
            ],
            [
                "https://example.com/griddap/b",
                "",
                "",
                "",
                "",
                "",
                "public",
                "Dataset B",
                "desc",
                "",
                "",
                "",
                "",
                "",
                "",
                "Inst",
                "dsB",
            ],
        ]
        fixture = {
            "table": {
                "columnNames": [
                    "griddap",
                    "Subset",
                    "tabledap",
                    "Make A Graph",
                    "wms",
                    "files",
                    "Accessible",
                    "Title",
                    "Summary",
                    "FGDC",
                    "ISO 19115",
                    "Info",
                    "Background Info",
                    "RSS",
                    "Email",
                    "Institution",
                    "Dataset ID",
                ],
                "rows": rows,
            }
        }
        respx.get(url__startswith=f"{COASTWATCH}/search/index.json").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await erddap_search_datasets(
            ctx, search_for="anything", items_per_page=2
        )

        assert "page=2" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_http_404_returns_error_msg(self, ctx: MagicMock) -> None:
        """A 404 from the server returns a user-friendly error, not a traceback."""
        respx.get(url__startswith=f"{COASTWATCH}/search/index.json").mock(
            return_value=httpx.Response(404)
        )

        result = await erddap_search_datasets(ctx, search_for="anything")

        assert "404" in result or "not found" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_http_500_returns_error_msg(self, ctx: MagicMock) -> None:
        """A 500 from the server returns a descriptive error message."""
        respx.get(url__startswith=f"{COASTWATCH}/search/index.json").mock(
            return_value=httpx.Response(500, text="<html><title>Error</title></html>")
        )

        result = await erddap_search_datasets(ctx, search_for="anything")

        assert "Error" in result or "error" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_timeout_returns_error_msg(self, ctx: MagicMock) -> None:
        """A timeout returns a friendly message suggesting smaller queries."""
        respx.get(url__startswith=f"{COASTWATCH}/search/index.json").mock(
            side_effect=httpx.ReadTimeout("read timed out")
        )

        result = await erddap_search_datasets(ctx, search_for="sst")

        assert "timed out" in result.lower()


# =========================================================================
# erddap_get_dataset_info
# =========================================================================
class TestGetDatasetInfo:
    """Tests for the erddap_get_dataset_info tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_info_returns_structured_markdown(
        self, ctx: MagicMock, info_fixture: dict
    ) -> None:
        """Dataset info is returned as structured markdown with key sections."""
        respx.get(url__startswith=f"{COASTWATCH}/info/erdMH1chlamday/index.json").mock(
            return_value=httpx.Response(200, json=info_fixture)
        )

        result = await erddap_get_dataset_info(
            ctx, server_url=COASTWATCH, dataset_id="erdMH1chlamday"
        )

        assert "## Dataset Info: erdMH1chlamday" in result
        assert "**Title**:" in result
        assert "Chlorophyll" in result
        assert "### Dimensions" in result
        assert "time" in result
        assert "latitude" in result
        assert "longitude" in result
        assert "### Variables" in result
        assert "chlorophyll" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_info_contains_spatial_coverage(
        self, ctx: MagicMock, info_fixture: dict
    ) -> None:
        """Dataset info includes latitude and longitude range from global attributes."""
        respx.get(url__startswith=f"{COASTWATCH}/info/erdMH1chlamday/index.json").mock(
            return_value=httpx.Response(200, json=info_fixture)
        )

        result = await erddap_get_dataset_info(
            ctx, server_url=COASTWATCH, dataset_id="erdMH1chlamday"
        )

        assert "Latitude Range" in result
        assert "Longitude Range" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_info_contains_time_coverage(
        self, ctx: MagicMock, info_fixture: dict
    ) -> None:
        """Dataset info includes time coverage start and end dates."""
        respx.get(url__startswith=f"{COASTWATCH}/info/erdMH1chlamday/index.json").mock(
            return_value=httpx.Response(200, json=info_fixture)
        )

        result = await erddap_get_dataset_info(
            ctx, server_url=COASTWATCH, dataset_id="erdMH1chlamday"
        )

        assert "Time Coverage" in result
        assert "2003" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_info_404_dataset_not_found(self, ctx: MagicMock) -> None:
        """Requesting info for a non-existent dataset returns a 404 error message."""
        respx.get(
            url__startswith=f"{COASTWATCH}/info/nonexistent_dataset/index.json"
        ).mock(return_value=httpx.Response(404))

        result = await erddap_get_dataset_info(
            ctx, server_url=COASTWATCH, dataset_id="nonexistent_dataset"
        )

        assert "404" in result or "not found" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_info_empty_response(self, ctx: MagicMock) -> None:
        """An empty info response returns a 'no info found' message."""
        empty = {
            "table": {
                "columnNames": [
                    "Row Type",
                    "Variable Name",
                    "Attribute Name",
                    "Data Type",
                    "Value",
                ],
                "rows": [],
            }
        }
        respx.get(url__startswith=f"{COASTWATCH}/info/emptyds/index.json").mock(
            return_value=httpx.Response(200, json=empty)
        )

        result = await erddap_get_dataset_info(
            ctx, server_url=COASTWATCH, dataset_id="emptyds"
        )

        assert "No info found" in result


# =========================================================================
# erddap_get_all_datasets
# =========================================================================
class TestGetAllDatasets:
    """Tests for the erddap_get_all_datasets tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_all_datasets_returns_markdown(
        self, ctx: MagicMock, all_datasets_fixture: dict
    ) -> None:
        """Listing all datasets produces a markdown table with dataset IDs."""
        respx.get(url__startswith=f"{COASTWATCH}/tabledap/allDatasets.json").mock(
            return_value=httpx.Response(200, json=all_datasets_fixture)
        )

        result = await erddap_get_all_datasets(ctx, server_url=COASTWATCH)

        assert "## All Datasets" in result
        assert "erdMH1chlamday" in result
        assert "total datasets" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_all_datasets_filter_by_protocol_griddap(
        self, ctx: MagicMock, all_datasets_fixture: dict
    ) -> None:
        """Filtering by protocol='griddap' excludes tabledap-only datasets."""
        respx.get(url__startswith=f"{COASTWATCH}/tabledap/allDatasets.json").mock(
            return_value=httpx.Response(200, json=all_datasets_fixture)
        )

        result = await erddap_get_all_datasets(
            ctx, server_url=COASTWATCH, protocol="griddap"
        )

        assert "Protocol: griddap" in result
        # cwwcNDBCMet and pmelTao5dayIso are tabledap-only -- should be excluded
        assert "cwwcNDBCMet" not in result
        assert "pmelTao5dayIso" not in result
        # griddap datasets should remain
        assert "erdMH1chlamday" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_all_datasets_filter_by_protocol_tabledap(
        self, ctx: MagicMock, all_datasets_fixture: dict
    ) -> None:
        """Filtering by protocol='tabledap' excludes griddap-only datasets."""
        respx.get(url__startswith=f"{COASTWATCH}/tabledap/allDatasets.json").mock(
            return_value=httpx.Response(200, json=all_datasets_fixture)
        )

        result = await erddap_get_all_datasets(
            ctx, server_url=COASTWATCH, protocol="tabledap"
        )

        assert "Protocol: tabledap" in result
        assert "cwwcNDBCMet" in result
        assert "erdMH1chlamday" not in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_all_datasets_filter_by_institution(
        self, ctx: MagicMock, all_datasets_fixture: dict
    ) -> None:
        """Filtering by institution narrows results to matching rows."""
        respx.get(url__startswith=f"{COASTWATCH}/tabledap/allDatasets.json").mock(
            return_value=httpx.Response(200, json=all_datasets_fixture)
        )

        result = await erddap_get_all_datasets(
            ctx, server_url=COASTWATCH, institution="NDBC"
        )

        assert "Institution: NDBC" in result
        assert "cwwcNDBCMet" in result
        # Others should be excluded
        assert "erdMH1chlamday" not in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_all_datasets_filter_by_search_text(
        self, ctx: MagicMock, all_datasets_fixture: dict
    ) -> None:
        """Filtering by search_text matches against title and summary."""
        respx.get(url__startswith=f"{COASTWATCH}/tabledap/allDatasets.json").mock(
            return_value=httpx.Response(200, json=all_datasets_fixture)
        )

        result = await erddap_get_all_datasets(
            ctx, server_url=COASTWATCH, search_text="chlorophyll"
        )

        assert "erdMH1chlamday" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_all_datasets_pagination(
        self, ctx: MagicMock, all_datasets_fixture: dict
    ) -> None:
        """Offset and limit correctly paginate the result set."""
        respx.get(url__startswith=f"{COASTWATCH}/tabledap/allDatasets.json").mock(
            return_value=httpx.Response(200, json=all_datasets_fixture)
        )

        result = await erddap_get_all_datasets(
            ctx, server_url=COASTWATCH, limit=2, offset=0
        )

        assert "Showing" in result
        # With 5 total datasets and limit=2, should suggest more
        assert "offset=2" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_all_datasets_empty_server(self, ctx: MagicMock) -> None:
        """An empty server returns a 'no datasets found' message."""
        empty = {"table": {"columnNames": ["datasetID"], "rows": []}}
        respx.get(url__startswith=f"{COASTWATCH}/tabledap/allDatasets.json").mock(
            return_value=httpx.Response(200, json=empty)
        )

        result = await erddap_get_all_datasets(ctx, server_url=COASTWATCH)

        assert "No datasets found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_all_datasets_connect_error(self, ctx: MagicMock) -> None:
        """A connection error returns a user-friendly message."""
        respx.get(url__startswith=f"{COASTWATCH}/tabledap/allDatasets.json").mock(
            side_effect=httpx.ConnectError("connection refused")
        )

        result = await erddap_get_all_datasets(ctx, server_url=COASTWATCH)

        assert "Could not connect" in result


# =========================================================================
# erddap_get_griddap_data
# =========================================================================
class TestGetGriddapData:
    """Tests for the erddap_get_griddap_data tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_griddap_returns_markdown(
        self, ctx: MagicMock, info_fixture: dict, griddap_fixture: dict
    ) -> None:
        """A griddap request with markdown format returns a formatted table."""
        # The tool first fetches dataset info, then the actual data
        respx.get(url__startswith=f"{COASTWATCH}/info/erdMH1chlamday/index.json").mock(
            return_value=httpx.Response(200, json=info_fixture)
        )
        respx.get(url__startswith=f"{COASTWATCH}/griddap/erdMH1chlamday.json").mock(
            return_value=httpx.Response(200, json=griddap_fixture)
        )

        result = await erddap_get_griddap_data(
            ctx,
            server_url=COASTWATCH,
            dataset_id="erdMH1chlamday",
            variables=["chlorophyll"],
            time_range=["2022-05-16T00:00:00Z", "2022-05-16T00:00:00Z"],
            latitude_range=[37.0, 38.0],
            longitude_range=[-122.0, -121.5],
        )

        assert "Griddap Data" in result
        assert "erdMH1chlamday" in result
        assert "chlorophyll" in result
        assert "grid points" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_griddap_returns_json(
        self, ctx: MagicMock, info_fixture: dict, griddap_fixture: dict
    ) -> None:
        """A griddap request with json format returns parseable JSON."""
        respx.get(url__startswith=f"{COASTWATCH}/info/erdMH1chlamday/index.json").mock(
            return_value=httpx.Response(200, json=info_fixture)
        )
        respx.get(url__startswith=f"{COASTWATCH}/griddap/erdMH1chlamday.json").mock(
            return_value=httpx.Response(200, json=griddap_fixture)
        )

        result = await erddap_get_griddap_data(
            ctx,
            server_url=COASTWATCH,
            dataset_id="erdMH1chlamday",
            variables=["chlorophyll"],
            time_range=["2022-05-16T00:00:00Z", "2022-05-16T00:00:00Z"],
            latitude_range=[37.0, 38.0],
            longitude_range=[-122.0, -121.5],
            response_format="json",
        )

        parsed = json.loads(result)
        assert parsed["dataset_id"] == "erdMH1chlamday"
        assert parsed["record_count"] == 6
        assert len(parsed["data"]) == 6
        assert parsed["variables"] == ["chlorophyll"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_griddap_default_variable(
        self, ctx: MagicMock, info_fixture: dict, griddap_fixture: dict
    ) -> None:
        """When no variable is specified, the tool auto-detects the first data variable."""
        respx.get(url__startswith=f"{COASTWATCH}/info/erdMH1chlamday/index.json").mock(
            return_value=httpx.Response(200, json=info_fixture)
        )
        respx.get(url__startswith=f"{COASTWATCH}/griddap/erdMH1chlamday.json").mock(
            return_value=httpx.Response(200, json=griddap_fixture)
        )

        result = await erddap_get_griddap_data(
            ctx,
            server_url=COASTWATCH,
            dataset_id="erdMH1chlamday",
            time_range=["last", "last"],
            latitude_range=[37.0, 38.0],
            longitude_range=[-122.0, -121.5],
            response_format="json",
        )

        parsed = json.loads(result)
        # chlorophyll is the only data variable (time/lat/lon are dimensions)
        assert parsed["variables"] == ["chlorophyll"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_griddap_large_range_warning(
        self, ctx: MagicMock, info_fixture: dict, griddap_fixture: dict
    ) -> None:
        """A large spatial range emits a warning about data volume."""
        respx.get(url__startswith=f"{COASTWATCH}/info/erdMH1chlamday/index.json").mock(
            return_value=httpx.Response(200, json=info_fixture)
        )
        respx.get(url__startswith=f"{COASTWATCH}/griddap/erdMH1chlamday.json").mock(
            return_value=httpx.Response(200, json=griddap_fixture)
        )

        result = await erddap_get_griddap_data(
            ctx,
            server_url=COASTWATCH,
            dataset_id="erdMH1chlamday",
            variables=["chlorophyll"],
            time_range=["last", "last"],
            latitude_range=[20.0, 50.0],
            longitude_range=[-130.0, -110.0],
        )

        assert "Warning" in result
        assert "stride" in result.lower() or "range" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_griddap_http_500_error(
        self, ctx: MagicMock, info_fixture: dict
    ) -> None:
        """A 500 error from the griddap data endpoint returns a descriptive message."""
        respx.get(url__startswith=f"{COASTWATCH}/info/erdMH1chlamday/index.json").mock(
            return_value=httpx.Response(200, json=info_fixture)
        )
        respx.get(url__startswith=f"{COASTWATCH}/griddap/erdMH1chlamday.json").mock(
            return_value=httpx.Response(
                500,
                text='<html><p class="error">Query error: variable not found</p></html>',
            )
        )

        result = await erddap_get_griddap_data(
            ctx,
            server_url=COASTWATCH,
            dataset_id="erdMH1chlamday",
            variables=["bad_var"],
            time_range=["last", "last"],
        )

        assert "Error" in result or "error" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_griddap_no_dimensions_in_info(self, ctx: MagicMock) -> None:
        """When dataset info has no dimensions, a helpful message is returned."""
        no_dim_info = {
            "table": {
                "columnNames": [
                    "Row Type",
                    "Variable Name",
                    "Attribute Name",
                    "Data Type",
                    "Value",
                ],
                "rows": [
                    ["attribute", "NC_GLOBAL", "title", "String", "Test Dataset"],
                ],
            }
        }
        respx.get(url__startswith=f"{COASTWATCH}/info/testds/index.json").mock(
            return_value=httpx.Response(200, json=no_dim_info)
        )

        result = await erddap_get_griddap_data(
            ctx,
            server_url=COASTWATCH,
            dataset_id="testds",
            variables=["sst"],
        )

        assert "Could not determine dimensions" in result


# =========================================================================
# erddap_get_tabledap_data
# =========================================================================
class TestGetTabledapData:
    """Tests for the erddap_get_tabledap_data tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_tabledap_returns_markdown(
        self, ctx: MagicMock, tabledap_fixture: dict
    ) -> None:
        """A tabledap request with markdown format returns a formatted table."""
        respx.get(url__startswith=f"{COASTWATCH}/tabledap/cwwcNDBCMet.json").mock(
            return_value=httpx.Response(200, json=tabledap_fixture)
        )

        result = await erddap_get_tabledap_data(
            ctx,
            server_url=COASTWATCH,
            dataset_id="cwwcNDBCMet",
            variables=["station", "time", "wtmp"],
            constraints={"station=": "46013", "time>=": "2024-01-15T00:00:00Z"},
            limit=10,
        )

        assert "Tabledap Data" in result
        assert "cwwcNDBCMet" in result
        assert "rows" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_tabledap_returns_json(
        self, ctx: MagicMock, tabledap_fixture: dict
    ) -> None:
        """A tabledap request with json format returns parseable JSON."""
        respx.get(url__startswith=f"{COASTWATCH}/tabledap/cwwcNDBCMet.json").mock(
            return_value=httpx.Response(200, json=tabledap_fixture)
        )

        result = await erddap_get_tabledap_data(
            ctx,
            server_url=COASTWATCH,
            dataset_id="cwwcNDBCMet",
            variables=["station", "time", "wtmp"],
            constraints={"station=": "46013"},
            response_format="json",
        )

        parsed = json.loads(result)
        assert parsed["dataset_id"] == "cwwcNDBCMet"
        assert parsed["record_count"] == 5
        assert len(parsed["data"]) == 5
        # First row should have expected keys
        row0 = parsed["data"][0]
        assert "station" in row0
        assert "wtmp" in row0

    @respx.mock
    @pytest.mark.asyncio
    async def test_tabledap_no_constraints_warning(
        self, ctx: MagicMock, tabledap_fixture: dict
    ) -> None:
        """Calling tabledap without constraints emits a warning about large datasets."""
        respx.get(url__startswith=f"{COASTWATCH}/tabledap/cwwcNDBCMet.json").mock(
            return_value=httpx.Response(200, json=tabledap_fixture)
        )

        result = await erddap_get_tabledap_data(
            ctx,
            server_url=COASTWATCH,
            dataset_id="cwwcNDBCMet",
        )

        assert "Warning" in result
        assert "No constraints" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_tabledap_json_no_constraints_warning(
        self, ctx: MagicMock, tabledap_fixture: dict
    ) -> None:
        """The no-constraints warning also appears in JSON format output."""
        respx.get(url__startswith=f"{COASTWATCH}/tabledap/cwwcNDBCMet.json").mock(
            return_value=httpx.Response(200, json=tabledap_fixture)
        )

        result = await erddap_get_tabledap_data(
            ctx,
            server_url=COASTWATCH,
            dataset_id="cwwcNDBCMet",
            response_format="json",
        )

        parsed = json.loads(result)
        assert "warnings" in parsed
        assert len(parsed["warnings"]) > 0

    @respx.mock
    @pytest.mark.asyncio
    async def test_tabledap_constraint_header_in_markdown(
        self, ctx: MagicMock, tabledap_fixture: dict
    ) -> None:
        """Constraints are shown in the markdown output metadata line."""
        respx.get(url__startswith=f"{COASTWATCH}/tabledap/cwwcNDBCMet.json").mock(
            return_value=httpx.Response(200, json=tabledap_fixture)
        )

        result = await erddap_get_tabledap_data(
            ctx,
            server_url=COASTWATCH,
            dataset_id="cwwcNDBCMet",
            constraints={"station=": "46013"},
        )

        assert "Constraints:" in result
        assert "46013" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_tabledap_timeout_returns_error_msg(self, ctx: MagicMock) -> None:
        """A timeout from the tabledap endpoint returns a friendly message."""
        respx.get(url__startswith=f"{COASTWATCH}/tabledap/cwwcNDBCMet.json").mock(
            side_effect=httpx.ReadTimeout("timed out")
        )

        result = await erddap_get_tabledap_data(
            ctx,
            server_url=COASTWATCH,
            dataset_id="cwwcNDBCMet",
            constraints={"station=": "46013"},
        )

        assert "timed out" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_tabledap_404_returns_error_msg(self, ctx: MagicMock) -> None:
        """A 404 from the tabledap endpoint returns a not-found error message."""
        respx.get(url__startswith=f"{COASTWATCH}/tabledap/nonexistent.json").mock(
            return_value=httpx.Response(404)
        )

        result = await erddap_get_tabledap_data(
            ctx,
            server_url=COASTWATCH,
            dataset_id="nonexistent",
            constraints={"time>=": "2024-01-01"},
        )

        assert "404" in result or "not found" in result.lower()


# =========================================================================
# Cross-cutting: HTML-instead-of-JSON detection
# =========================================================================
class TestHtmlErrorDetection:
    """Tests that verify the client rejects HTML responses masquerading as data."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_html_content_type_raises_on_search(self, ctx: MagicMock) -> None:
        """When ERDDAP returns text/html for a .json URL, the error handler catches it."""
        respx.get(url__startswith=f"{COASTWATCH}/search/index.json").mock(
            return_value=httpx.Response(
                200,
                text="<html><body>Oops</body></html>",
                headers={"content-type": "text/html"},
            )
        )

        result = await erddap_search_datasets(ctx, search_for="sst")

        # The error handler should produce a message about parsing or HTML
        assert (
            "error" in result.lower()
            or "html" in result.lower()
            or "parsing" in result.lower()
        )

    @respx.mock
    @pytest.mark.asyncio
    async def test_html_content_type_raises_on_info(self, ctx: MagicMock) -> None:
        """HTML response on dataset info endpoint is handled gracefully."""
        respx.get(url__startswith=f"{COASTWATCH}/info/bad/index.json").mock(
            return_value=httpx.Response(
                200,
                text="<html><body>Error</body></html>",
                headers={"content-type": "text/html; charset=UTF-8"},
            )
        )

        result = await erddap_get_dataset_info(
            ctx, server_url=COASTWATCH, dataset_id="bad"
        )

        assert "error" in result.lower() or "html" in result.lower()
