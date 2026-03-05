"""Validation tests for goes-mcp models and URL building."""

import pytest

from goes_mcp.models import (
    ABI_BANDS,
    COMPOSITE_PRODUCTS,
    COVERAGES,
    PRODUCTS,
    RESOLUTIONS,
    SATELLITES,
    SECTORS,
    SLIDER_PRODUCTS,
    SLIDER_SECTORS,
    satellite_key_to_id,
    validate_coverage,
    validate_product,
    validate_resolution,
    validate_sector,
)


class TestSatelliteValidation:
    """Tests for satellite key validation."""

    def test_goes_19_to_id(self) -> None:
        """Convert goes-19 key to GOES19 CDN ID."""
        assert satellite_key_to_id("goes-19") == "GOES19"

    def test_goes_18_to_id(self) -> None:
        """Convert goes-18 key to GOES18 CDN ID."""
        assert satellite_key_to_id("goes-18") == "GOES18"

    def test_case_insensitive(self) -> None:
        """Satellite keys should be case-insensitive."""
        assert satellite_key_to_id("GOES-19") == "GOES19"
        assert satellite_key_to_id("Goes-18") == "GOES18"

    def test_invalid_satellite_raises(self) -> None:
        """Unknown satellite key should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown satellite"):
            satellite_key_to_id("goes-17")

    def test_satellites_dict_has_both(self) -> None:
        """SATELLITES dict should contain both operational satellites."""
        assert "goes-19" in SATELLITES
        assert "goes-18" in SATELLITES
        assert len(SATELLITES) == 2


class TestProductValidation:
    """Tests for product code validation."""

    def test_all_16_bands_exist(self) -> None:
        """All 16 ABI bands should be in the product catalog."""
        for i in range(1, 17):
            band_id = f"{i:02d}"
            assert band_id in ABI_BANDS, f"Band {band_id} missing"

    def test_composite_products_exist(self) -> None:
        """All named composite products should exist."""
        expected = {"GEOCOLOR", "AirMass", "Sandwich", "FireTemperature", "Dust", "DMW"}
        assert expected == set(COMPOSITE_PRODUCTS.keys())

    def test_products_is_union(self) -> None:
        """PRODUCTS should contain all bands plus all composites."""
        assert len(PRODUCTS) == len(ABI_BANDS) + len(COMPOSITE_PRODUCTS)
        for key in ABI_BANDS:
            assert key in PRODUCTS
        for key in COMPOSITE_PRODUCTS:
            assert key in PRODUCTS

    def test_validate_product_exact_match(self) -> None:
        """Exact product codes should validate correctly."""
        assert validate_product("GEOCOLOR") == "GEOCOLOR"
        assert validate_product("13") == "13"
        assert validate_product("01") == "01"

    def test_validate_product_case_insensitive(self) -> None:
        """Composite product names should be case-insensitive."""
        assert validate_product("geocolor") == "GEOCOLOR"
        assert validate_product("airmass") == "AirMass"

    def test_validate_product_invalid_raises(self) -> None:
        """Unknown product should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown product"):
            validate_product("INVALID")


class TestCoverageValidation:
    """Tests for coverage code validation."""

    def test_conus_coverage(self) -> None:
        """CONUS coverage should return correct path."""
        assert validate_coverage("CONUS") == "CONUS"

    def test_full_disk_coverage(self) -> None:
        """FD coverage should return correct path."""
        assert validate_coverage("FD") == "FD"

    def test_coverage_case_insensitive(self) -> None:
        """Coverage codes should be case-insensitive."""
        assert validate_coverage("conus") == "CONUS"
        assert validate_coverage("fd") == "FD"

    def test_invalid_coverage_raises(self) -> None:
        """Unknown coverage should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown coverage"):
            validate_coverage("MESOSCALE")


class TestSectorValidation:
    """Tests for sector code validation."""

    def test_all_sectors_exist(self) -> None:
        """All expected sectors should be in SECTORS dict."""
        expected = {"se", "ne", "car", "taw", "pr"}
        assert expected == set(SECTORS.keys())

    def test_validate_sector_returns_path(self) -> None:
        """Sector validation should return CDN path with SECTOR/ prefix."""
        assert validate_sector("se") == "SECTOR/se"
        assert validate_sector("car") == "SECTOR/car"

    def test_invalid_sector_raises(self) -> None:
        """Unknown sector should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown sector"):
            validate_sector("midwest")


class TestResolutionValidation:
    """Tests for resolution validation."""

    def test_all_resolutions_exist(self) -> None:
        """All expected resolutions should be in RESOLUTIONS dict."""
        expected = {
            "thumbnail",
            "625x375",
            "1250x750",
            "2500x1500",
            "5000x3000",
            "latest",
        }
        assert expected == set(RESOLUTIONS.keys())

    def test_validate_resolution_returns_filename(self) -> None:
        """Resolution validation should return the correct filename."""
        assert validate_resolution("thumbnail") == "thumbnail.jpg"
        assert validate_resolution("1250x750") == "1250x750.jpg"
        assert validate_resolution("latest") == "latest.jpg"

    def test_invalid_resolution_raises(self) -> None:
        """Unknown resolution should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown resolution"):
            validate_resolution("100x100")


class TestSliderMappings:
    """Tests for SLIDER API mappings."""

    def test_slider_sectors_cover_all(self) -> None:
        """SLIDER mapping should cover all coverages and sectors."""
        for key in COVERAGES:
            assert key in SLIDER_SECTORS, (
                f"Coverage '{key}' missing from SLIDER_SECTORS"
            )
        for key in SECTORS:
            assert key in SLIDER_SECTORS, f"Sector '{key}' missing from SLIDER_SECTORS"

    def test_slider_products_cover_all(self) -> None:
        """SLIDER mapping should cover all products."""
        for key in PRODUCTS:
            assert key in SLIDER_PRODUCTS, (
                f"Product '{key}' missing from SLIDER_PRODUCTS"
            )
