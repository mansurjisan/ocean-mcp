"""Validation tests for nhc-mcp Pydantic models and helper functions."""

import pytest

from nhc_mcp.models import (
    SAFFIR_SIMPSON,
    Basin,
    StormClassification,
    classify_wind_speed,
)


class TestBasinEnum:
    """Tests for the Basin enum."""

    def test_basin_has_three_values(self):
        """Basin enum should contain exactly three members."""
        assert len(Basin) == 3

    def test_basin_atlantic(self):
        """Basin.AL should have the value 'al'."""
        assert Basin.AL.value == "al"

    def test_basin_east_pacific(self):
        """Basin.EP should have the value 'ep'."""
        assert Basin.EP.value == "ep"

    def test_basin_central_pacific(self):
        """Basin.CP should have the value 'cp'."""
        assert Basin.CP.value == "cp"

    def test_basin_rejects_invalid_value(self):
        """Basin should raise ValueError for an unrecognised value."""
        with pytest.raises(ValueError):
            Basin("xx")

    def test_basin_rejects_uppercase(self):
        """Basin should reject uppercase variants that are not defined."""
        with pytest.raises(ValueError):
            Basin("AL")


class TestStormClassification:
    """Tests for the StormClassification enum."""

    def test_classification_has_nine_values(self):
        """StormClassification should contain exactly nine members."""
        assert len(StormClassification) == 9

    def test_classification_values(self):
        """All expected classification codes should be present."""
        expected = {"TD", "TS", "HU", "SD", "SS", "EX", "LO", "DB", "WV"}
        actual = {member.value for member in StormClassification}
        assert actual == expected

    def test_classification_tropical_depression(self):
        """StormClassification.TD should have the value 'TD'."""
        assert StormClassification.TD.value == "TD"

    def test_classification_hurricane(self):
        """StormClassification.HU should have the value 'HU'."""
        assert StormClassification.HU.value == "HU"


class TestSaffirSimpson:
    """Tests for the SAFFIR_SIMPSON constant."""

    def test_saffir_simpson_is_non_empty(self):
        """SAFFIR_SIMPSON should be a non-empty list."""
        assert len(SAFFIR_SIMPSON) > 0

    def test_saffir_simpson_ordered_by_descending_threshold(self):
        """Thresholds in SAFFIR_SIMPSON should be in descending order."""
        thresholds = [entry[0] for entry in SAFFIR_SIMPSON]
        assert thresholds == sorted(thresholds, reverse=True)

    def test_saffir_simpson_has_seven_entries(self):
        """SAFFIR_SIMPSON should contain exactly seven entries."""
        assert len(SAFFIR_SIMPSON) == 7

    def test_saffir_simpson_lowest_threshold_is_zero(self):
        """The lowest threshold should be 0 (Tropical Depression)."""
        assert SAFFIR_SIMPSON[-1][0] == 0


class TestClassifyWindSpeed:
    """Tests for the classify_wind_speed helper function."""

    @pytest.mark.parametrize(
        "wind_kt, expected",
        [
            (30, "Tropical Depression"),
            (50, "Tropical Storm"),
            (75, "Category 1"),
            (90, "Category 2"),
            (100, "Category 3"),
            (120, "Category 4"),
            (150, "Category 5"),
        ],
    )
    def test_classify_wind_speed_categories(self, wind_kt, expected):
        """classify_wind_speed should return the correct category for the given wind speed."""
        assert classify_wind_speed(wind_kt) == expected

    def test_classify_wind_speed_zero(self):
        """A wind speed of 0 should return Tropical Depression."""
        assert classify_wind_speed(0) == "Tropical Depression"

    def test_classify_wind_speed_boundary_34(self):
        """A wind speed of exactly 34 kt should return Tropical Storm."""
        assert classify_wind_speed(34) == "Tropical Storm"

    def test_classify_wind_speed_boundary_64(self):
        """A wind speed of exactly 64 kt should return Category 1."""
        assert classify_wind_speed(64) == "Category 1"

    def test_classify_wind_speed_boundary_137(self):
        """A wind speed of exactly 137 kt should return Category 5."""
        assert classify_wind_speed(137) == "Category 5"
