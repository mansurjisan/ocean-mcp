"""Validation tests for stofs-mcp Pydantic models and constants."""

import pytest

from stofs_mcp.models import (
    COOPS_VALIDATION_DATUMS,
    MODEL_CYCLES,
    MODEL_DATUMS,
    MODEL_LAG_HOURS,
    Region,
    STOFSModel,
    STOFSProduct,
)


class TestSTOFSModel:
    """Tests for the STOFSModel enum."""

    def test_2d_global_value(self):
        """STOFSModel.GLOBAL_2D should have value '2d_global'."""
        assert STOFSModel.GLOBAL_2D.value == "2d_global"

    def test_3d_atlantic_value(self):
        """STOFSModel.ATLANTIC_3D should have value '3d_atlantic'."""
        assert STOFSModel.ATLANTIC_3D.value == "3d_atlantic"

    def test_model_has_exactly_two_members(self):
        """STOFSModel should have exactly two members."""
        assert len(STOFSModel) == 2

    def test_rejects_invalid_value(self):
        """STOFSModel should raise ValueError for unknown model strings."""
        with pytest.raises(ValueError):
            STOFSModel("invalid_model")

    def test_rejects_empty_string(self):
        """STOFSModel should raise ValueError for an empty string."""
        with pytest.raises(ValueError):
            STOFSModel("")

    def test_value_as_string(self):
        """STOFSModel members should have correct .value strings."""
        assert STOFSModel.GLOBAL_2D.value == "2d_global"
        assert STOFSModel.ATLANTIC_3D.value == "3d_atlantic"


class TestSTOFSProduct:
    """Tests for the STOFSProduct enum."""

    def test_cwl_value(self):
        """STOFSProduct.CWL should have value 'cwl'."""
        assert STOFSProduct.CWL.value == "cwl"

    def test_htp_value(self):
        """STOFSProduct.HTP should have value 'htp'."""
        assert STOFSProduct.HTP.value == "htp"

    def test_swl_value(self):
        """STOFSProduct.SWL should have value 'swl'."""
        assert STOFSProduct.SWL.value == "swl"

    def test_product_has_exactly_three_members(self):
        """STOFSProduct should have exactly three members."""
        assert len(STOFSProduct) == 3

    def test_rejects_invalid_product(self):
        """STOFSProduct should raise ValueError for unknown product strings."""
        with pytest.raises(ValueError):
            STOFSProduct("invalid_product")


class TestRegion:
    """Tests for the Region enum."""

    def test_east_coast_value(self):
        """Region.EAST_COAST should have value 'east_coast'."""
        assert Region.EAST_COAST.value == "east_coast"

    def test_gulf_value(self):
        """Region.GULF should have value 'gulf'."""
        assert Region.GULF.value == "gulf"

    def test_west_coast_value(self):
        """Region.WEST_COAST should have value 'west_coast'."""
        assert Region.WEST_COAST.value == "west_coast"

    def test_alaska_value(self):
        """Region.ALASKA should have value 'alaska'."""
        assert Region.ALASKA.value == "alaska"

    def test_hawaii_value(self):
        """Region.HAWAII should have value 'hawaii'."""
        assert Region.HAWAII.value == "hawaii"

    def test_puerto_rico_value(self):
        """Region.PUERTO_RICO should have value 'puerto_rico'."""
        assert Region.PUERTO_RICO.value == "puerto_rico"

    def test_region_has_exactly_six_members(self):
        """Region should have exactly six members."""
        assert len(Region) == 6

    def test_rejects_invalid_region(self):
        """Region should raise ValueError for unknown region strings."""
        with pytest.raises(ValueError):
            Region("atlantic")


class TestModelCycles:
    """Tests for the MODEL_CYCLES constant."""

    def test_has_2d_global_entry(self):
        """MODEL_CYCLES should have an entry for '2d_global'."""
        assert "2d_global" in MODEL_CYCLES

    def test_has_3d_atlantic_entry(self):
        """MODEL_CYCLES should have an entry for '3d_atlantic'."""
        assert "3d_atlantic" in MODEL_CYCLES

    def test_2d_global_has_four_cycles(self):
        """2d_global should have four cycle hours."""
        assert len(MODEL_CYCLES["2d_global"]) == 4

    def test_3d_atlantic_has_one_cycle(self):
        """3d_atlantic should have one cycle hour."""
        assert len(MODEL_CYCLES["3d_atlantic"]) == 1

    def test_2d_global_cycles_are_valid_hours(self):
        """All 2d_global cycle hours should be two-digit strings."""
        for cycle in MODEL_CYCLES["2d_global"]:
            assert cycle in {"00", "06", "12", "18"}

    def test_3d_atlantic_cycle_is_12z(self):
        """3d_atlantic should only run at 12z."""
        assert MODEL_CYCLES["3d_atlantic"] == ["12"]


class TestModelDatums:
    """Tests for the MODEL_DATUMS constant."""

    def test_has_2d_global_entry(self):
        """MODEL_DATUMS should have an entry for '2d_global'."""
        assert "2d_global" in MODEL_DATUMS

    def test_has_3d_atlantic_entry(self):
        """MODEL_DATUMS should have an entry for '3d_atlantic'."""
        assert "3d_atlantic" in MODEL_DATUMS

    def test_2d_global_datum_is_lmsl(self):
        """2d_global datum should be LMSL."""
        assert MODEL_DATUMS["2d_global"] == "LMSL"

    def test_3d_atlantic_datum_is_navd88(self):
        """3d_atlantic datum should be NAVD88."""
        assert MODEL_DATUMS["3d_atlantic"] == "NAVD88"


class TestCoopsValidationDatums:
    """Tests for the COOPS_VALIDATION_DATUMS constant."""

    def test_has_2d_global_entry(self):
        """COOPS_VALIDATION_DATUMS should have an entry for '2d_global'."""
        assert "2d_global" in COOPS_VALIDATION_DATUMS

    def test_has_3d_atlantic_entry(self):
        """COOPS_VALIDATION_DATUMS should have an entry for '3d_atlantic'."""
        assert "3d_atlantic" in COOPS_VALIDATION_DATUMS

    def test_2d_global_coops_datum_is_msl(self):
        """2d_global CO-OPS validation datum should be MSL."""
        assert COOPS_VALIDATION_DATUMS["2d_global"] == "MSL"

    def test_3d_atlantic_coops_datum_is_navd(self):
        """3d_atlantic CO-OPS validation datum should be NAVD."""
        assert COOPS_VALIDATION_DATUMS["3d_atlantic"] == "NAVD"


class TestModelLagHours:
    """Tests for the MODEL_LAG_HOURS constant."""

    def test_has_2d_global_entry(self):
        """MODEL_LAG_HOURS should have an entry for '2d_global'."""
        assert "2d_global" in MODEL_LAG_HOURS

    def test_has_3d_atlantic_entry(self):
        """MODEL_LAG_HOURS should have an entry for '3d_atlantic'."""
        assert "3d_atlantic" in MODEL_LAG_HOURS

    def test_lag_hours_are_positive_integers(self):
        """All lag hour values should be positive integers."""
        for model, lag in MODEL_LAG_HOURS.items():
            assert isinstance(lag, int), f"Lag for {model} should be an int"
            assert lag > 0, f"Lag for {model} should be positive"

    def test_3d_atlantic_lag_greater_than_2d_global(self):
        """3d_atlantic should have a longer lag than 2d_global."""
        assert MODEL_LAG_HOURS["3d_atlantic"] > MODEL_LAG_HOURS["2d_global"]
