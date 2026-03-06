"""Unit tests for schism-mcp tool functions.

Tests cover reference tools, parsing tools, validation tools, and doc tools.
No network access required for most tests.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from schism_mcp.client import SchismClient

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
