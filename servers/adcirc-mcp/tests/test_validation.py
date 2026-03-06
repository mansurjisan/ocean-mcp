"""Tests for ADCIRC parameter registry, error patterns, and enum validation.

Verifies the embedded domain knowledge in models.py is complete and consistent.
"""

from adcirc_mcp.models import (
    ADCIRC_ERROR_PATTERNS,
    ADCIRC_PARAMETERS,
    NODAL_ATTRIBUTES,
    NWS_VALUES,
    TIDAL_CONSTITUENTS,
    ParamCategory,
)


class TestParameterRegistry:
    """Tests for the ADCIRC parameter dictionary."""

    def test_parameter_count(self) -> None:
        """Registry has at least 30 parameters."""
        assert len(ADCIRC_PARAMETERS) >= 30

    def test_all_parameters_have_description(self) -> None:
        """Every parameter has a non-empty description."""
        for name, param in ADCIRC_PARAMETERS.items():
            assert "description" in param, f"{name} missing description"
            assert len(param["description"]) > 0, f"{name} has empty description"

    def test_all_parameters_have_category(self) -> None:
        """Every parameter has a valid category."""
        for name, param in ADCIRC_PARAMETERS.items():
            assert "category" in param, f"{name} missing category"
            assert isinstance(param["category"], ParamCategory), (
                f"{name} has invalid category"
            )

    def test_all_parameters_have_type(self) -> None:
        """Every parameter has a type."""
        for name, param in ADCIRC_PARAMETERS.items():
            assert "type" in param, f"{name} missing type"

    def test_key_parameters_present(self) -> None:
        """Critical parameters are in the registry."""
        expected = ["DTDP", "RNDAY", "NWS", "IHOT", "ICS", "IM", "NOLIBF", "H0", "TAU0"]
        for name in expected:
            assert name in ADCIRC_PARAMETERS, f"Missing key parameter: {name}"


class TestNWSValues:
    """Tests for the NWS reference dictionary."""

    def test_nws_has_zero(self) -> None:
        """NWS=0 (no forcing) is defined."""
        assert 0 in NWS_VALUES
        assert "no" in NWS_VALUES[0]["description"].lower()

    def test_nws_common_values(self) -> None:
        """Common NWS values are defined."""
        for val in [0, 8, 12, -12, 16]:
            assert val in NWS_VALUES, f"Missing NWS={val}"

    def test_nws_files_required(self) -> None:
        """All NWS entries specify required files."""
        for val, info in NWS_VALUES.items():
            assert "files_required" in info, f"NWS={val} missing files_required"
            assert isinstance(info["files_required"], list)


class TestTidalConstituents:
    """Tests for the tidal constituent reference."""

    def test_major_constituents_present(self) -> None:
        """Major tidal constituents are defined."""
        expected = ["M2", "S2", "N2", "K1", "O1", "P1"]
        for name in expected:
            assert name in TIDAL_CONSTITUENTS, f"Missing constituent: {name}"

    def test_constituents_have_period(self) -> None:
        """All constituents have period_hours."""
        for name, const in TIDAL_CONSTITUENTS.items():
            assert "period_hours" in const, f"{name} missing period_hours"
            assert const["period_hours"] > 0, f"{name} has invalid period"

    def test_m2_period(self) -> None:
        """M2 has the correct period."""
        assert abs(TIDAL_CONSTITUENTS["M2"]["period_hours"] - 12.4206) < 0.01


class TestNodalAttributes:
    """Tests for the nodal attribute reference."""

    def test_mannings_n_present(self) -> None:
        """Manning's n is defined."""
        assert "mannings_n_at_sea_floor" in NODAL_ATTRIBUTES

    def test_attributes_have_description(self) -> None:
        """All attributes have descriptions."""
        for name, attr in NODAL_ATTRIBUTES.items():
            assert "description" in attr, f"{name} missing description"

    def test_attributes_have_defaults(self) -> None:
        """All attributes have default values."""
        for name, attr in NODAL_ATTRIBUTES.items():
            assert "default_value" in attr, f"{name} missing default_value"


class TestErrorPatterns:
    """Tests for the error diagnosis patterns."""

    def test_pattern_count(self) -> None:
        """At least 5 error patterns defined."""
        assert len(ADCIRC_ERROR_PATTERNS) >= 5

    def test_patterns_have_required_fields(self) -> None:
        """Each pattern has keywords, diagnosis, and fixes."""
        for i, pattern in enumerate(ADCIRC_ERROR_PATTERNS):
            assert "keywords" in pattern, f"Pattern {i} missing keywords"
            assert "diagnosis" in pattern, f"Pattern {i} missing diagnosis"
            assert "fixes" in pattern, f"Pattern {i} missing fixes"
            assert len(pattern["keywords"]) > 0
            assert len(pattern["fixes"]) > 0

    def test_cfl_pattern_exists(self) -> None:
        """A CFL-related pattern exists."""
        has_cfl = any(
            any("cfl" in kw.lower() for kw in p["keywords"])
            for p in ADCIRC_ERROR_PATTERNS
        )
        assert has_cfl, "Missing CFL error pattern"


class TestParamCategory:
    """Tests for the ParamCategory enum."""

    def test_categories_count(self) -> None:
        """At least 5 categories defined."""
        assert len(ParamCategory) >= 5

    def test_time_stepping_exists(self) -> None:
        """TIME_STEPPING category exists."""
        assert ParamCategory.TIME_STEPPING == "time_stepping"

    def test_forcing_exists(self) -> None:
        """FORCING category exists."""
        assert ParamCategory.FORCING == "forcing"
