"""Validation tests for recon-mcp Pydantic models and constants."""

import pytest

from recon_mcp.models import (
    AIRCRAFT_CODES,
    PRODUCT_DIRS,
    Basin,
    ReconProduct,
)


class TestBasinEnum:
    """Tests for the Basin enum."""

    def test_basin_values(self):
        """Basin enum contains al, ep, and cp."""
        assert Basin.AL.value == "al"
        assert Basin.EP.value == "ep"
        assert Basin.CP.value == "cp"

    def test_basin_has_exactly_three_members(self):
        """Basin enum has exactly three members."""
        assert len(Basin) == 3

    def test_basin_rejects_invalid_value(self):
        """Basin enum raises ValueError for unknown basin codes."""
        with pytest.raises(ValueError):
            Basin("wp")
        with pytest.raises(ValueError):
            Basin("atlantic")
        with pytest.raises(ValueError):
            Basin("")


class TestReconProductEnum:
    """Tests for the ReconProduct enum."""

    def test_product_values(self):
        """ReconProduct enum contains hdob, vdm, and dropsonde."""
        assert ReconProduct.HDOB.value == "hdob"
        assert ReconProduct.VDM.value == "vdm"
        assert ReconProduct.DROPSONDE.value == "dropsonde"

    def test_product_has_exactly_three_members(self):
        """ReconProduct enum has exactly three members."""
        assert len(ReconProduct) == 3

    def test_product_rejects_invalid_value(self):
        """ReconProduct enum raises ValueError for unknown product types."""
        with pytest.raises(ValueError):
            ReconProduct("sfmr")
        with pytest.raises(ValueError):
            ReconProduct("radar")


class TestProductDirs:
    """Tests for the PRODUCT_DIRS mapping."""

    def test_known_product_basin_tuples_exist(self):
        """PRODUCT_DIRS has entries for all known (product, basin) combinations."""
        expected_keys = [
            ("hdob", "al"),
            ("hdob", "ep"),
            ("vdm", "al"),
            ("vdm", "ep"),
            ("dropsonde", "al"),
            ("dropsonde", "ep"),
        ]
        for key in expected_keys:
            assert key in PRODUCT_DIRS, f"Missing PRODUCT_DIRS entry for {key}"

    def test_product_dirs_values_are_wmo_headers(self):
        """PRODUCT_DIRS values are non-empty uppercase WMO directory names."""
        for key, value in PRODUCT_DIRS.items():
            assert isinstance(value, str), f"Value for {key} is not a string"
            assert len(value) > 0, f"Value for {key} is empty"
            assert value == value.upper(), f"Value '{value}' for {key} is not uppercase"

    def test_hdob_atlantic_dir(self):
        """HDOB Atlantic directory is AHONT1."""
        assert PRODUCT_DIRS[("hdob", "al")] == "AHONT1"

    def test_vdm_atlantic_dir(self):
        """VDM Atlantic directory is REPNT2."""
        assert PRODUCT_DIRS[("vdm", "al")] == "REPNT2"


class TestAircraftCodes:
    """Tests for the AIRCRAFT_CODES mapping."""

    def test_known_aircraft_codes_exist(self):
        """AIRCRAFT_CODES maps known single-letter codes U, H, I, N."""
        expected_codes = {"U", "H", "I", "N"}
        assert expected_codes.issubset(set(AIRCRAFT_CODES.keys()))

    def test_aircraft_code_u_is_usaf(self):
        """Aircraft code U maps to the USAF WC-130J."""
        assert "USAF" in AIRCRAFT_CODES["U"]
        assert "WC-130J" in AIRCRAFT_CODES["U"]

    def test_aircraft_code_h_is_noaa_p3(self):
        """Aircraft code H maps to NOAA N42RF (P-3)."""
        assert "NOAA" in AIRCRAFT_CODES["H"]
        assert "N42RF" in AIRCRAFT_CODES["H"]

    def test_aircraft_codes_values_are_nonempty_strings(self):
        """All AIRCRAFT_CODES values are non-empty descriptive strings."""
        for code, description in AIRCRAFT_CODES.items():
            assert isinstance(description, str), (
                f"Description for '{code}' is not a string"
            )
            assert len(description) > 0, f"Description for '{code}' is empty"
