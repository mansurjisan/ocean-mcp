"""Tests for SCHISM parameter registry, error patterns, and enum validation.

Verifies the embedded domain knowledge in models.py is complete and consistent.
"""

from schism_mcp.models import (
    BC_TYPES,
    SCHISM_ERROR_PATTERNS,
    SCHISM_PARAMETERS,
    TIDAL_CONSTITUENTS,
    VGRID_TYPES,
    NamelistSection,
)


class TestParameterRegistry:
    """Tests for the SCHISM parameter dictionary."""

    def test_parameter_count(self) -> None:
        """Registry has at least 25 parameters."""
        assert len(SCHISM_PARAMETERS) >= 25

    def test_all_parameters_have_description(self) -> None:
        """Every parameter has a non-empty description."""
        for name, param in SCHISM_PARAMETERS.items():
            assert "description" in param, f"{name} missing description"
            assert len(param["description"]) > 0, f"{name} has empty description"

    def test_all_parameters_have_section(self) -> None:
        """Every parameter has a valid section."""
        for name, param in SCHISM_PARAMETERS.items():
            assert "section" in param, f"{name} missing section"
            assert isinstance(param["section"], NamelistSection), (
                f"{name} has invalid section"
            )

    def test_all_parameters_have_type(self) -> None:
        """Every parameter has a type."""
        for name, param in SCHISM_PARAMETERS.items():
            assert "type" in param, f"{name} missing type"

    def test_key_parameters_present(self) -> None:
        """Critical parameters are in the registry."""
        expected = ["dt", "rnday", "ihfskip", "nhot", "ics", "nws", "nspool", "h0"]
        for name in expected:
            assert name in SCHISM_PARAMETERS, f"Missing key parameter: {name}"


class TestVgridTypes:
    """Tests for vertical grid type reference."""

    def test_lsc2_defined(self) -> None:
        """LSC2 type (ivcor=1) is defined."""
        assert 1 in VGRID_TYPES
        assert VGRID_TYPES[1]["name"] == "LSC2"

    def test_sz_defined(self) -> None:
        """SZ type (ivcor=2) is defined."""
        assert 2 in VGRID_TYPES
        assert VGRID_TYPES[2]["name"] == "SZ"


class TestBCTypes:
    """Tests for boundary condition type reference."""

    def test_tidal_bc_defined(self) -> None:
        """Tidal BC type (3) is defined."""
        assert 3 in BC_TYPES
        assert "tidal" in BC_TYPES[3]["name"].lower()

    def test_no_bc_defined(self) -> None:
        """No-BC type (0) is defined."""
        assert 0 in BC_TYPES


class TestTidalConstituents:
    """Tests for the tidal constituent reference."""

    def test_major_constituents(self) -> None:
        """Major constituents are defined."""
        for name in ["M2", "S2", "K1", "O1"]:
            assert name in TIDAL_CONSTITUENTS

    def test_m2_period(self) -> None:
        """M2 period is correct."""
        assert abs(TIDAL_CONSTITUENTS["M2"]["period_hours"] - 12.4206) < 0.01


class TestErrorPatterns:
    """Tests for the error diagnosis patterns."""

    def test_pattern_count(self) -> None:
        """At least 5 error patterns defined."""
        assert len(SCHISM_ERROR_PATTERNS) >= 5

    def test_patterns_have_required_fields(self) -> None:
        """Each pattern has keywords, diagnosis, and fixes."""
        for i, pattern in enumerate(SCHISM_ERROR_PATTERNS):
            assert "keywords" in pattern, f"Pattern {i} missing keywords"
            assert "diagnosis" in pattern, f"Pattern {i} missing diagnosis"
            assert "fixes" in pattern, f"Pattern {i} missing fixes"
            assert len(pattern["keywords"]) > 0
            assert len(pattern["fixes"]) > 0


class TestNamelistSection:
    """Tests for the NamelistSection enum."""

    def test_core_exists(self) -> None:
        """CORE section exists."""
        assert NamelistSection.CORE == "CORE"

    def test_opt_exists(self) -> None:
        """OPT section exists."""
        assert NamelistSection.OPT == "OPT"

    def test_schout_exists(self) -> None:
        """SCHOUT section exists."""
        assert NamelistSection.SCHOUT == "SCHOUT"
