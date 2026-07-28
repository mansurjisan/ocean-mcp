"""Unit tests for schism-mcp tool functions.

Tests cover reference tools, parsing tools, validation tools, and doc tools.
No network access required for most tests.
"""

from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from schism_mcp.client import (
    RetryTransport,
    SchismClient,
    SchismClientError,
    handle_schism_error,
)
from schism_mcp.models import SCHISM_DOCS_BASE

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    """Load a text fixture file."""
    return (FIXTURES_DIR / name).read_text()


def _make_ctx(client: SchismClient) -> MagicMock:
    """Build a mock MCP Context whose lifespan_context holds the given SchismClient."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"schism_client": client}
    return ctx


@pytest.fixture
def schism_client() -> SchismClient:
    """Create a bare SchismClient."""
    return SchismClient()


@pytest.fixture
def ctx(schism_client: SchismClient) -> MagicMock:
    """Create a mock Context wired to the SchismClient fixture."""
    return _make_ctx(schism_client)


@pytest.mark.asyncio
async def test_client_uses_retry_transport() -> None:
    """The shared httpx client is mounted on the RetryTransport."""
    c = SchismClient()
    client = await c._get_client()
    try:
        assert isinstance(client._transport, RetryTransport)
    finally:
        await c.close()


class TestExplainParameter:
    """Tests for the schism_explain_parameter tool."""

    @pytest.mark.asyncio
    async def test_explain_known_parameter(self, ctx: MagicMock) -> None:
        """Explain a known param.nml parameter."""
        from schism_mcp.tools.reference import schism_explain_parameter

        result = await schism_explain_parameter(ctx, parameter="dt")
        assert "dt" in result
        assert "seconds" in result.lower()

    @pytest.mark.asyncio
    async def test_explain_nspool(self, ctx: MagicMock) -> None:
        """Explain nspool parameter."""
        from schism_mcp.tools.reference import schism_explain_parameter

        result = await schism_explain_parameter(ctx, parameter="nspool")
        assert "nspool" in result
        assert "SCHOUT" in result

    @pytest.mark.asyncio
    async def test_explain_tidal_constituent(self, ctx: MagicMock) -> None:
        """Explain a tidal constituent."""
        from schism_mcp.tools.reference import schism_explain_parameter

        result = await schism_explain_parameter(ctx, parameter="M2")
        assert "M2" in result
        assert "12.4206" in result

    @pytest.mark.asyncio
    async def test_explain_vgrid_type(self, ctx: MagicMock) -> None:
        """Explain a vertical grid type by name."""
        from schism_mcp.tools.reference import schism_explain_parameter

        result = await schism_explain_parameter(ctx, parameter="LSC2")
        assert "LSC2" in result

    @pytest.mark.asyncio
    async def test_explain_unknown_parameter(self, ctx: MagicMock) -> None:
        """Unknown parameter returns helpful message."""
        from schism_mcp.tools.reference import schism_explain_parameter

        result = await schism_explain_parameter(ctx, parameter="NONEXISTENT")
        assert "not found" in result.lower()


class TestListParameters:
    """Tests for the schism_list_parameters tool."""

    @pytest.mark.asyncio
    async def test_list_all(self, ctx: MagicMock) -> None:
        """List all parameters."""
        from schism_mcp.tools.reference import schism_list_parameters

        result = await schism_list_parameters(ctx)
        assert "dt" in result
        assert "nspool" in result
        assert "Tidal Constituents" in result

    @pytest.mark.asyncio
    async def test_list_filtered_section(self, ctx: MagicMock) -> None:
        """List parameters filtered by section."""
        from schism_mcp.tools.reference import schism_list_parameters

        result = await schism_list_parameters(ctx, section="CORE")
        assert "dt" in result
        assert "&CORE" in result


class TestParseParamNmlTool:
    """Tests for the schism_parse_param_nml tool."""

    @pytest.mark.asyncio
    async def test_parse_from_content(self, ctx: MagicMock) -> None:
        """Parse param.nml from content string."""
        from schism_mcp.tools.parsing import schism_parse_param_nml

        content = _load_fixture("param_nml_minimal.txt")
        result = await schism_parse_param_nml(ctx, content=content)
        assert "param.nml Configuration Summary" in result
        assert "100.0" in result  # dt
        assert "30.0" in result  # rnday

    @pytest.mark.asyncio
    async def test_parse_file_not_found(self, ctx: MagicMock) -> None:
        """A missing param.nml path surfaces a clear SCHISM Error, not a raw repr."""
        from schism_mcp.tools.parsing import schism_parse_param_nml

        result = await schism_parse_param_nml(
            ctx, file_path="/nonexistent/does_not_exist_param.nml"
        )
        assert result.startswith("SCHISM Error:")
        assert "file not found" in result.lower()


class TestParseHgridTool:
    """Tests for the schism_parse_hgrid tool."""

    @pytest.mark.asyncio
    async def test_parse_from_content(self, ctx: MagicMock) -> None:
        """Parse hgrid.gr3 from content string."""
        from schism_mcp.tools.parsing import schism_parse_hgrid

        content = _load_fixture("hgrid_header.txt")
        result = await schism_parse_hgrid(ctx, content=content)
        assert "hgrid.gr3 Mesh Summary" in result
        assert "1,100" in result  # nodes

    @pytest.mark.asyncio
    async def test_bounding_box_notes_partial_scan(self, ctx: MagicMock) -> None:
        """Bounding box/max depth computed from a partial node scan say so,
        instead of presenting a partial result as if it covered the full mesh."""
        from schism_mcp.tools.parsing import schism_parse_hgrid

        # fixture declares 1,100 nodes but only has 5 node data lines.
        content = _load_fixture("hgrid_header.txt")
        result = await schism_parse_hgrid(ctx, content=content)
        assert "Bounding box" in result
        assert "from first 5 of 1,100 nodes" in result
        assert "Max depth" in result

    @pytest.mark.asyncio
    async def test_parse_file_not_found(self, ctx: MagicMock) -> None:
        """A missing hgrid.gr3 path surfaces a clear SCHISM Error, not a raw repr."""
        from schism_mcp.tools.parsing import schism_parse_hgrid

        result = await schism_parse_hgrid(
            ctx, file_path="/nonexistent/does_not_exist_hgrid.gr3"
        )
        assert result.startswith("SCHISM Error:")
        assert "file not found" in result.lower()


class TestParseVgridTool:
    """Tests for the schism_parse_vgrid tool."""

    @pytest.mark.asyncio
    async def test_parse_from_content(self, ctx: MagicMock) -> None:
        """Parse vgrid.in from content string."""
        from schism_mcp.tools.parsing import schism_parse_vgrid

        content = _load_fixture("vgrid_sample.txt")
        result = await schism_parse_vgrid(ctx, content=content)
        assert "vgrid.in" in result
        assert "SZ" in result
        assert "20" in result  # nvrt


class TestParseBctidesTool:
    """Tests for the schism_parse_bctides tool."""

    @pytest.mark.asyncio
    async def test_parse_from_content(self, ctx: MagicMock) -> None:
        """Parse bctides.in from content string."""
        from schism_mcp.tools.parsing import schism_parse_bctides

        content = _load_fixture("bctides_sample.txt")
        result = await schism_parse_bctides(ctx, content=content)
        assert "bctides.in" in result
        assert "M2" in result
        assert "3" in result  # nbfr


class TestValidateConfig:
    """Tests for the schism_validate_config tool."""

    @pytest.mark.asyncio
    async def test_validate_good_config(self, ctx: MagicMock) -> None:
        """Validate a good configuration produces no errors."""
        from schism_mcp.tools.validation import schism_validate_config

        content = _load_fixture("param_nml_minimal.txt")
        result = await schism_validate_config(ctx, param_nml_content=content)
        assert "Validation" in result
        assert "0 errors" in result

    @pytest.mark.asyncio
    async def test_validate_bad_config(self, ctx: MagicMock) -> None:
        """Validate a bad configuration detects errors."""
        from schism_mcp.tools.validation import schism_validate_config

        content = _load_fixture("param_nml_errors.txt")
        result = await schism_validate_config(ctx, param_nml_content=content)
        assert "error" in result.lower()

    @pytest.mark.asyncio
    async def test_validate_file_not_found(self, ctx: MagicMock) -> None:
        """A missing param_nml_path surfaces a clear SCHISM Error, not a raw repr."""
        from schism_mcp.tools.validation import schism_validate_config

        result = await schism_validate_config(
            ctx, param_nml_path="/nonexistent/does_not_exist_param.nml"
        )
        assert result.startswith("SCHISM Error:")
        assert "file not found" in result.lower()


class TestDiagnoseError:
    """Tests for the schism_diagnose_error tool."""

    @pytest.mark.asyncio
    async def test_diagnose_nan(self, ctx: MagicMock) -> None:
        """Diagnose a NaN divergence error."""
        from schism_mcp.tools.validation import schism_diagnose_error

        result = await schism_diagnose_error(
            ctx, error_text="Solution diverged with NaN values"
        )
        assert "NaN" in result or "diverge" in result.lower()
        assert "Suggested fixes" in result

    @pytest.mark.asyncio
    async def test_diagnose_unknown(self, ctx: MagicMock) -> None:
        """Unknown error returns suggestions."""
        from schism_mcp.tools.validation import schism_diagnose_error

        result = await schism_diagnose_error(ctx, error_text="Random unknown error")
        assert "No known error patterns" in result


class TestDocTools:
    """Tests for documentation search/fetch tools.

    schism_search_docs never hits the network (it filters a static known-page
    list), but schism_fetch_docs does — those tests mock the SCHISM docs site
    with respx so they run without network access. Regression coverage for
    the actual live URLs (a site restructure is exactly the kind of bug static
    mocks can't catch) lives in test_live.py.
    """

    @pytest.mark.asyncio
    async def test_search_docs_param_nml(self, ctx: MagicMock) -> None:
        """Search for 'param.nml' resolves to the real param.html page."""
        from schism_mcp.tools.docs import schism_search_docs

        result = await schism_search_docs(ctx, query="param.nml")
        assert "param.nml" in result
        assert f"{SCHISM_DOCS_BASE}/input-output/param.html" in result

    @pytest.mark.asyncio
    async def test_search_docs_no_results(self, ctx: MagicMock) -> None:
        """A query matching no known page returns a helpful message."""
        from schism_mcp.tools.docs import schism_search_docs

        result = await schism_search_docs(ctx, query="zzz_nonexistent_topic_zzz")
        assert "No results found" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_docs_direct_path(self, ctx: MagicMock) -> None:
        """Fetching an explicit .html path hits that exact URL under the
        current /master/ docs base and returns its stripped text content."""
        from schism_mcp.tools.docs import schism_fetch_docs

        html = (
            "<html><body><h1>param.nml</h1><p>Main SCHISM namelist.</p></body></html>"
        )
        route = respx.get(f"{SCHISM_DOCS_BASE}/input-output/param.html").mock(
            return_value=httpx.Response(200, text=html)
        )

        result = await schism_fetch_docs(ctx, topic="input-output/param.html")

        assert route.called
        assert "Main SCHISM namelist" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_docs_search_fallback(self, ctx: MagicMock) -> None:
        """A non-.html topic is resolved via search_docs first, then fetched."""
        from schism_mcp.tools.docs import schism_fetch_docs

        html = "<html><body><p>bctides.in defines tidal boundary conditions.</p></body></html>"
        route = respx.get(f"{SCHISM_DOCS_BASE}/input-output/bctides.html").mock(
            return_value=httpx.Response(200, text=html)
        )

        result = await schism_fetch_docs(ctx, topic="bctides.in")

        assert route.called
        assert "tidal boundary conditions" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_docs_404_reports_error(self, ctx: MagicMock) -> None:
        """A broken/stale URL surfaces as a documentation error, not a crash."""
        from schism_mcp.tools.docs import schism_fetch_docs

        respx.get(f"{SCHISM_DOCS_BASE}/input-output/does-not-exist.html").mock(
            return_value=httpx.Response(404, text="Not Found")
        )

        result = await schism_fetch_docs(ctx, topic="input-output/does-not-exist.html")
        assert "error" in result.lower()

    @respx.mock
    @pytest.mark.asyncio
    async def test_fetch_docs_http_error(self, ctx: MagicMock) -> None:
        """An upstream HTTP error surfaces a clear SCHISM Error, not a raw repr."""
        from schism_mcp.tools.docs import schism_fetch_docs

        route = respx.get(f"{SCHISM_DOCS_BASE}/input-output/param.html").mock(
            return_value=httpx.Response(503)
        )

        result = await schism_fetch_docs(ctx, topic="input-output/param.html")
        assert route.called
        assert result.startswith("SCHISM Error:")
        assert "503" in result


class TestHandleSchismError:
    """Direct unit tests for the handle_schism_error formatter."""

    def test_client_error(self) -> None:
        """SchismClientError is passed through with the server prefix."""
        result = handle_schism_error(SchismClientError("File too large (150.0 MB)."))
        assert result == "SCHISM Error: File too large (150.0 MB)."

    def test_file_not_found(self) -> None:
        """FileNotFoundError names the problem and a concrete next step."""
        try:
            open("/nonexistent/does_not_exist.txt")
        except FileNotFoundError as e:
            result = handle_schism_error(e)
        assert result.startswith("SCHISM Error:")
        assert "file not found" in result.lower()
        assert "file_path" in result

    def test_os_error(self) -> None:
        """A generic OSError is distinguished from FileNotFoundError."""
        result = handle_schism_error(OSError("disk quota exceeded"))
        assert result.startswith("SCHISM Error:")
        assert "could not read file" in result.lower()

    def test_http_status_error(self) -> None:
        """httpx.HTTPStatusError names the status code and suggests a next step."""
        request = httpx.Request("GET", "https://schism-dev.github.io/schism/x.html")
        response = httpx.Response(500, request=request)
        error = httpx.HTTPStatusError("fail", request=request, response=response)
        result = handle_schism_error(error)
        assert result.startswith("SCHISM Error:")
        assert "500" in result
        assert "schism_search_docs" in result

    def test_timeout_error(self) -> None:
        """httpx.TimeoutException gets a clear timeout message."""
        result = handle_schism_error(httpx.TimeoutException("timed out"))
        assert result.startswith("SCHISM Error:")
        assert "timed out" in result.lower()

    def test_generic_exception_fallback(self) -> None:
        """An unrecognized exception type still gets the server prefix, not a
        bare repr — the type name is included instead of being swallowed."""
        result = handle_schism_error(ValueError("something unexpected"))
        assert result == "SCHISM Error: ValueError: something unexpected"
