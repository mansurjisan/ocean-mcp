"""Validation tests for goes-mcp models and URL building."""

import pytest

from goes_mcp.models import (
    ABI_BANDS,
    COMPOSITE_PRODUCTS,
    COVERAGES,
    DEFAULT_RESOLUTION_BY_KIND,
    PRODUCTS,
    RESOLUTIONS_BY_KIND,
    SATELLITES,
    SECTORS,
    SLIDER_COVERAGES,
    SLIDER_PRODUCTS,
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
    """Tests for per-coverage-kind resolution validation.

    STAR CDN resolution ladders are coverage-shaped (verified live): CONUS
    is landscape, FD and SECTOR are each square at different pixel sizes.
    """

    def test_conus_resolutions(self) -> None:
        """CONUS ladder should have its documented sizes plus the two aliases."""
        expected = {
            "thumbnail",
            "625x375",
            "1250x750",
            "2500x1500",
            "5000x3000",
            "latest",
        }
        assert expected == set(RESOLUTIONS_BY_KIND["CONUS"].keys())

    def test_fd_resolutions(self) -> None:
        """FD ladder is square and uses a different pixel ladder than CONUS."""
        expected = {
            "thumbnail",
            "339x339",
            "678x678",
            "1808x1808",
            "5424x5424",
            "10848x10848",
            "latest",
        }
        assert expected == set(RESOLUTIONS_BY_KIND["FD"].keys())

    def test_sector_resolutions(self) -> None:
        """SECTOR ladder is square and uses yet another pixel ladder."""
        expected = {
            "thumbnail",
            "300x300",
            "600x600",
            "1200x1200",
            "2400x2400",
            "latest",
        }
        assert expected == set(RESOLUTIONS_BY_KIND["SECTOR"].keys())

    def test_validate_resolution_returns_filename(self) -> None:
        """Resolution validation should return the correct filename."""
        assert validate_resolution("thumbnail", "CONUS") == "thumbnail.jpg"
        assert validate_resolution("1250x750", "CONUS") == "1250x750.jpg"
        assert validate_resolution("latest", "CONUS") == "latest.jpg"
        assert validate_resolution("1808x1808", "FD") == "1808x1808.jpg"
        assert validate_resolution("1200x1200", "SECTOR") == "1200x1200.jpg"

    def test_invalid_resolution_raises(self) -> None:
        """Unknown resolution should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown resolution"):
            validate_resolution("100x100", "CONUS")

    def test_resolution_wrong_kind_raises(self) -> None:
        """A resolution valid for one coverage kind must be rejected for another.

        This is the actual bug that made goes_get_sector_image and FD
        imagery 404 before per-coverage validation: CONUS's '1250x750'
        doesn't exist for FD or SECTOR, and the error should say so.
        """
        with pytest.raises(ValueError, match="Unknown resolution '1250x750' for FD"):
            validate_resolution("1250x750", "FD")
        with pytest.raises(
            ValueError, match="Unknown resolution '1808x1808' for SECTOR"
        ):
            validate_resolution("1808x1808", "SECTOR")

    def test_error_lists_valid_options_for_kind(self) -> None:
        """The error message should list the valid sizes for that coverage."""
        with pytest.raises(ValueError) as exc_info:
            validate_resolution("1250x750", "FD")
        msg = str(exc_info.value)
        assert "1808x1808" in msg
        assert "10848x10848" in msg

    def test_default_resolution_by_kind_are_valid(self) -> None:
        """Each per-kind default must itself be a valid resolution for that kind."""
        for kind, default in DEFAULT_RESOLUTION_BY_KIND.items():
            assert default in RESOLUTIONS_BY_KIND[kind]


class TestSliderMappings:
    """Tests for SLIDER API mappings."""

    def test_slider_coverages_are_conus_and_fd_only(self) -> None:
        """SLIDER only publishes CONUS and FD — regional sectors 404 there.

        Verified live against slider.cira.colostate.edu: 'southeast',
        'northeast', 'caribbean', 'tropical_atlantic', and 'puerto_rico'
        (the old SLIDER_SECTORS mappings for se/ne/car/taw/pr) all 404.
        """
        assert set(SLIDER_COVERAGES.keys()) == {"CONUS", "FD"}
        for key in COVERAGES:
            assert key in SLIDER_COVERAGES, (
                f"Coverage '{key}' missing from SLIDER_COVERAGES"
            )
        for key in SECTORS:
            assert key not in SLIDER_COVERAGES, (
                f"Sector '{key}' should not be in SLIDER_COVERAGES — "
                "SLIDER doesn't publish it"
            )

    def test_slider_products_cover_all(self) -> None:
        """SLIDER mapping should cover all products."""
        for key in PRODUCTS:
            assert key in SLIDER_PRODUCTS, (
                f"Product '{key}' missing from SLIDER_PRODUCTS"
            )
