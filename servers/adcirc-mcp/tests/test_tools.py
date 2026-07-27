"""Unit tests for adcirc-mcp tool functions with mocked HTTP responses.

Tests cover reference tools, parsing tools, validation tools, and doc tools.
All HTTP calls are mocked using respx; no network access is required.
"""

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from adcirc_mcp.client import (
    ADCIRCClient,
    ADCIRCClientError,
    RetryTransport,
    WIKI_API_URL,
    handle_adcirc_error,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    """Load a text fixture file."""
    return (FIXTURES_DIR / name).read_text()


def _make_ctx(client: ADCIRCClient) -> MagicMock:
    """Build a mock MCP Context whose lifespan_context holds the given ADCIRCClient."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"adcirc_client": client}
    return ctx


@pytest.fixture
def adcirc_client() -> ADCIRCClient:
    """Create a bare ADCIRCClient."""
    return ADCIRCClient()


@pytest.fixture
def ctx(adcirc_client: ADCIRCClient) -> MagicMock:
    """Create a mock Context wired to the ADCIRCClient fixture."""
    return _make_ctx(adcirc_client)


@pytest.mark.asyncio
async def test_client_uses_retry_transport() -> None:
    """The shared httpx client is mounted on the RetryTransport."""
    c = ADCIRCClient()
    client = await c._get_client()
    try:
        assert isinstance(client._transport, RetryTransport)
    finally:
        await c.close()


class TestExplainParameter:
    """Tests for the adcirc_explain_parameter tool."""

    @pytest.mark.asyncio
    async def test_explain_known_parameter(self, ctx: MagicMock) -> None:
        """Explain a known fort.15 parameter."""
        from adcirc_mcp.tools.reference import adcirc_explain_parameter

        result = await adcirc_explain_parameter(ctx, parameter="DTDP")
        assert "DTDP" in result
        assert "seconds" in result.lower()

    @pytest.mark.asyncio
    async def test_explain_nws_parameter(self, ctx: MagicMock) -> None:
        """Explain NWS shows all NWS value reference."""
        from adcirc_mcp.tools.reference import adcirc_explain_parameter

        result = await adcirc_explain_parameter(ctx, parameter="NWS")
        assert "NWS" in result
        assert "meteorological" in result.lower()

    @pytest.mark.asyncio
    async def test_explain_tidal_constituent(self, ctx: MagicMock) -> None:
        """Explain a tidal constituent."""
        from adcirc_mcp.tools.reference import adcirc_explain_parameter

        result = await adcirc_explain_parameter(ctx, parameter="M2")
        assert "M2" in result
        assert "12.4206" in result

    @pytest.mark.asyncio
    async def test_explain_nodal_attribute(self, ctx: MagicMock) -> None:
        """Explain a nodal attribute."""
        from adcirc_mcp.tools.reference import adcirc_explain_parameter

        result = await adcirc_explain_parameter(
            ctx, parameter="mannings_n_at_sea_floor"
        )
        assert "Manning" in result

    @pytest.mark.asyncio
    async def test_explain_unknown_parameter(self, ctx: MagicMock) -> None:
        """Unknown parameter returns helpful message."""
        from adcirc_mcp.tools.reference import adcirc_explain_parameter

        result = await adcirc_explain_parameter(ctx, parameter="NONEXISTENT")
        assert "not found" in result.lower()


class TestListParameters:
    """Tests for the adcirc_list_parameters tool."""

    @pytest.mark.asyncio
    async def test_list_all(self, ctx: MagicMock) -> None:
        """List all parameters returns content from multiple categories."""
        from adcirc_mcp.tools.reference import adcirc_list_parameters

        result = await adcirc_list_parameters(ctx)
        assert "DTDP" in result
        assert "NWS" in result
        assert "Tidal Constituents" in result

    @pytest.mark.asyncio
    async def test_list_filtered_category(self, ctx: MagicMock) -> None:
        """List parameters filtered by category."""
        from adcirc_mcp.tools.reference import adcirc_list_parameters

        result = await adcirc_list_parameters(ctx, category="time_stepping")
        assert "DTDP" in result
        assert "Time Stepping" in result


class TestParseFort15Tool:
    """Tests for the adcirc_parse_fort15 tool."""

    @pytest.mark.asyncio
    async def test_parse_from_content(self, ctx: MagicMock) -> None:
        """Parse fort.15 from content string."""
        from adcirc_mcp.tools.parsing import adcirc_parse_fort15

        content = _load_fixture("fort15_minimal.txt")
        result = await adcirc_parse_fort15(ctx, content=content)
        assert "Fort.15 Configuration Summary" in result
        assert "2.0 seconds" in result
        assert "5.0 days" in result

    @pytest.mark.asyncio
    async def test_parse_shows_tidal_info(self, ctx: MagicMock) -> None:
        """Parse shows tidal constituent information."""
        from adcirc_mcp.tools.parsing import adcirc_parse_fort15

        content = _load_fixture("fort15_minimal.txt")
        result = await adcirc_parse_fort15(ctx, content=content)
        assert "M2" in result
        assert "S2" in result

    @pytest.mark.asyncio
    async def test_parse_file_not_found(self, ctx: MagicMock) -> None:
        """A missing fort.15 path surfaces a clear ADCIRC Error, not a raw repr."""
        from adcirc_mcp.tools.parsing import adcirc_parse_fort15

        result = await adcirc_parse_fort15(
            ctx, file_path="/nonexistent/does_not_exist_fort15.txt"
        )
        assert result.startswith("ADCIRC Error:")
        assert "file not found" in result.lower()


class TestParseFort14Tool:
    """Tests for the adcirc_parse_fort14 tool."""

    @pytest.mark.asyncio
    async def test_parse_from_content(self, ctx: MagicMock) -> None:
        """Parse fort.14 header from content string."""
        from adcirc_mcp.tools.parsing import adcirc_parse_fort14

        content = _load_fixture("fort14_header.txt")
        result = await adcirc_parse_fort14(ctx, content=content)
        assert "Fort.14 Mesh Summary" in result
        assert "500" in result  # nodes

    @pytest.mark.asyncio
    async def test_partial_scan_boundary_caveat(self, ctx: MagicMock) -> None:
        """A header-only scan that never reaches the boundary section says so
        explicitly instead of silently omitting boundary info."""
        from adcirc_mcp.tools.parsing import adcirc_parse_fort14

        # fixture declares 1000 elements / 500 nodes but only has 5 node lines,
        # so the boundary section (starting around line 2 + 500 + 1000) is far
        # beyond what's actually in the file.
        content = _load_fixture("fort14_header.txt")
        result = await adcirc_parse_fort14(ctx, content=content)
        assert "Open boundaries" in result
        assert "not present in the scanned header region" in result

    @pytest.mark.asyncio
    async def test_parse_file_not_found(self, ctx: MagicMock) -> None:
        """A missing fort.14 path surfaces a clear ADCIRC Error, not a raw repr."""
        from adcirc_mcp.tools.parsing import adcirc_parse_fort14

        result = await adcirc_parse_fort14(
            ctx, file_path="/nonexistent/does_not_exist_fort14.txt"
        )
        assert result.startswith("ADCIRC Error:")
        assert "file not found" in result.lower()


class TestValidateConfig:
    """Tests for the adcirc_validate_config tool."""

    @pytest.mark.asyncio
    async def test_validate_good_config(self, ctx: MagicMock) -> None:
        """Validate a good configuration produces no errors."""
        from adcirc_mcp.tools.validation import adcirc_validate_config

        content = _load_fixture("fort15_minimal.txt")
        result = await adcirc_validate_config(ctx, fort15_content=content)
        assert "Validation" in result
        assert "0 errors" in result

    @pytest.mark.asyncio
    async def test_validate_bad_config(self, ctx: MagicMock) -> None:
        """Validate a bad configuration detects errors."""
        from adcirc_mcp.tools.validation import adcirc_validate_config

        content = _load_fixture("fort15_errors.txt")
        result = await adcirc_validate_config(ctx, fort15_content=content)
        assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_validate_with_cfl(self, ctx: MagicMock) -> None:
        """Validate with CFL check."""
        from adcirc_mcp.tools.validation import adcirc_validate_config

        content = _load_fixture("fort15_minimal.txt")
        result = await adcirc_validate_config(
            ctx,
            fort15_content=content,
            min_edge_length=500.0,
            max_depth=20.0,
        )
        assert "CFL" in result

    @pytest.mark.asyncio
    async def test_validate_file_not_found(self, ctx: MagicMock) -> None:
        """A missing fort15_path surfaces a clear ADCIRC Error, not a raw repr."""
        from adcirc_mcp.tools.validation import adcirc_validate_config

        result = await adcirc_validate_config(
            ctx, fort15_path="/nonexistent/does_not_exist_fort15.txt"
        )
        assert result.startswith("ADCIRC Error:")
        assert "file not found" in result.lower()


class TestDiagnoseError:
    """Tests for the adcirc_diagnose_error tool."""

    @pytest.mark.asyncio
    async def test_diagnose_cfl(self, ctx: MagicMock) -> None:
        """Diagnose a CFL violation error."""
        from adcirc_mcp.tools.validation import adcirc_diagnose_error

        result = await adcirc_diagnose_error(
            ctx, error_text="Model blew up with CFL violation"
        )
        assert "CFL" in result
        assert "Suggested fixes" in result

    @pytest.mark.asyncio
    async def test_diagnose_unknown(self, ctx: MagicMock) -> None:
        """Unknown error returns suggestions."""
        from adcirc_mcp.tools.validation import adcirc_diagnose_error

        result = await adcirc_diagnose_error(ctx, error_text="Random unknown error xyz")
        assert "No known error patterns" in result


class TestDocTools:
    """Tests for documentation fetching tools."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_search_docs(self, ctx: MagicMock) -> None:
        """Search docs returns results from wiki API."""
        from adcirc_mcp.tools.docs import adcirc_search_docs

        mock_response = {
            "query": {
                "search": [
                    {"title": "Fort.15", "snippet": "Control file for <b>ADCIRC</b>"},
                    {"title": "NWS", "snippet": "Wind and pressure <b>forcing</b>"},
                ]
            }
        }
        respx.get(WIKI_API_URL).mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        result = await adcirc_search_docs(ctx, query="fort.15")
        assert "Fort.15" in result
        assert "results found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_docs(self, ctx: MagicMock) -> None:
        """Fetch docs returns wiki page content."""
        from adcirc_mcp.tools.docs import adcirc_fetch_docs

        mock_response = {
            "parse": {
                "text": {
                    "*": "<p>The fort.15 file is the main control file for ADCIRC.</p>"
                }
            }
        }
        respx.get(WIKI_API_URL).mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        result = await adcirc_fetch_docs(ctx, topic="Fort.15")
        assert "fort.15" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_docs_page_not_found(self, ctx: MagicMock) -> None:
        """A wiki 'page not found' response surfaces a clear ADCIRC Error with
        the actionable next step baked into the message, not a raw repr."""
        from adcirc_mcp.tools.docs import adcirc_fetch_docs

        mock_response = {"error": {"info": "The page you specified doesn't exist"}}
        respx.get(WIKI_API_URL).mock(
            return_value=httpx.Response(200, json=mock_response)
        )

        result = await adcirc_fetch_docs(ctx, topic="Nonexistent Page")
        assert result.startswith("ADCIRC Error:")
        assert "adcirc_search_docs" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_docs_http_error(self, ctx: MagicMock) -> None:
        """An upstream HTTP error surfaces a clear ADCIRC Error, not a raw repr."""
        from adcirc_mcp.tools.docs import adcirc_fetch_docs

        respx.get(WIKI_API_URL).mock(return_value=httpx.Response(503))

        result = await adcirc_fetch_docs(ctx, topic="Fort.15")
        assert result.startswith("ADCIRC Error:")
        assert "503" in result


class TestHandleAdcircError:
    """Direct unit tests for the handle_adcirc_error formatter."""

    def test_client_error(self) -> None:
        """ADCIRCClientError is passed through with the server prefix."""
        result = handle_adcirc_error(ADCIRCClientError("File too large (150.0 MB)."))
        assert result == "ADCIRC Error: File too large (150.0 MB)."

    def test_file_not_found(self) -> None:
        """FileNotFoundError names the problem and a concrete next step."""
        try:
            open("/nonexistent/does_not_exist.txt")
        except FileNotFoundError as e:
            result = handle_adcirc_error(e)
        assert result.startswith("ADCIRC Error:")
        assert "file not found" in result.lower()
        assert "file_path" in result

    def test_os_error(self) -> None:
        """A generic OSError is distinguished from FileNotFoundError."""
        result = handle_adcirc_error(OSError("disk quota exceeded"))
        assert result.startswith("ADCIRC Error:")
        assert "could not read file" in result.lower()

    def test_http_status_error(self) -> None:
        """httpx.HTTPStatusError names the status code and suggests a next step."""
        request = httpx.Request("GET", "https://wiki.adcirc.org/api.php")
        response = httpx.Response(500, request=request)
        error = httpx.HTTPStatusError("fail", request=request, response=response)
        result = handle_adcirc_error(error)
        assert result.startswith("ADCIRC Error:")
        assert "500" in result
        assert "adcirc_search_docs" in result

    def test_timeout_error(self) -> None:
        """httpx.TimeoutException gets a clear timeout message."""
        result = handle_adcirc_error(httpx.TimeoutException("timed out"))
        assert result.startswith("ADCIRC Error:")
        assert "timed out" in result.lower()

    def test_generic_exception_fallback(self) -> None:
        """An unrecognized exception type still gets the server prefix, not a
        bare repr — the type name is included instead of being swallowed."""
        result = handle_adcirc_error(ValueError("something unexpected"))
        assert result == "ADCIRC Error: ValueError: something unexpected"
