"""Pydantic/enum validation tests for coops-mcp models."""

import pytest

from coops_mcp.models import (
    CurrentsProduct,
    DateShorthand,
    Datum,
    Interval,
    MetProduct,
    StationType,
    TimeZone,
    Units,
)


class TestDatum:
    """Tests for the Datum enum."""

    def test_valid_datum_values(self):
        """All defined datum values should be constructible from their string."""
        expected = [
            "MLLW",
            "MHHW",
            "MSL",
            "NAVD",
            "STND",
            "MHW",
            "MLW",
            "MTL",
            "IGLD",
            "LWD",
        ]
        for val in expected:
            assert Datum(val) == val

    def test_invalid_datum_raises(self):
        """An invalid datum string should raise ValueError."""
        with pytest.raises(ValueError):
            Datum("INVALID")

    def test_datum_member_count(self):
        """Datum should have exactly 10 members."""
        assert len(Datum) == 10


class TestUnits:
    """Tests for the Units enum."""

    def test_valid_units(self):
        """Both unit systems should be constructible."""
        assert Units("metric") == "metric"
        assert Units("english") == "english"

    def test_invalid_units_raises(self):
        """An invalid unit string should raise ValueError."""
        with pytest.raises(ValueError):
            Units("imperial")

    def test_units_member_count(self):
        """Units should have exactly 2 members."""
        assert len(Units) == 2


class TestTimeZone:
    """Tests for the TimeZone enum."""

    def test_valid_timezones(self):
        """All timezone values should be constructible."""
        assert TimeZone("gmt") == "gmt"
        assert TimeZone("lst") == "lst"
        assert TimeZone("lst_ldt") == "lst_ldt"

    def test_invalid_timezone_raises(self):
        """An invalid timezone string should raise ValueError."""
        with pytest.raises(ValueError):
            TimeZone("utc")

    def test_timezone_member_count(self):
        """TimeZone should have exactly 3 members."""
        assert len(TimeZone) == 3


class TestInterval:
    """Tests for the Interval enum."""

    def test_valid_intervals(self):
        """All interval values should be constructible."""
        assert Interval("6") == "6"
        assert Interval("h") == "h"
        assert Interval("hilo") == "hilo"

    def test_invalid_interval_raises(self):
        """An invalid interval string should raise ValueError."""
        with pytest.raises(ValueError):
            Interval("15")

    def test_interval_member_count(self):
        """Interval should have exactly 3 members."""
        assert len(Interval) == 3


class TestDateShorthand:
    """Tests for the DateShorthand enum."""

    def test_valid_shorthands(self):
        """All date shorthand values should be constructible."""
        assert DateShorthand("today") == "today"
        assert DateShorthand("latest") == "latest"
        assert DateShorthand("recent") == "recent"

    def test_invalid_shorthand_raises(self):
        """An invalid date shorthand should raise ValueError."""
        with pytest.raises(ValueError):
            DateShorthand("yesterday")

    def test_shorthand_member_count(self):
        """DateShorthand should have exactly 3 members."""
        assert len(DateShorthand) == 3


class TestStationType:
    """Tests for the StationType enum."""

    def test_valid_station_types(self):
        """All station type values should be constructible."""
        expected = [
            "waterlevels",
            "currentpredictions",
            "waterlevelsandmet",
            "tcoon",
            "nwlon",
            "ports",
        ]
        for val in expected:
            assert StationType(val) == val

    def test_invalid_station_type_raises(self):
        """An invalid station type should raise ValueError."""
        with pytest.raises(ValueError):
            StationType("buoy")

    def test_station_type_member_count(self):
        """StationType should have exactly 6 members."""
        assert len(StationType) == 6


class TestMetProduct:
    """Tests for the MetProduct enum."""

    def test_valid_met_products(self):
        """All meteorological product values should be constructible."""
        expected = [
            "wind",
            "air_temperature",
            "water_temperature",
            "air_pressure",
            "humidity",
            "conductivity",
            "salinity",
            "visibility",
            "air_gap",
        ]
        for val in expected:
            assert MetProduct(val) == val

    def test_invalid_met_product_raises(self):
        """An invalid met product should raise ValueError."""
        with pytest.raises(ValueError):
            MetProduct("rainfall")

    def test_met_product_member_count(self):
        """MetProduct should have exactly 9 members."""
        assert len(MetProduct) == 9


class TestCurrentsProduct:
    """Tests for the CurrentsProduct enum."""

    def test_valid_currents_products(self):
        """Both currents product values should be constructible."""
        assert CurrentsProduct("currents") == "currents"
        assert CurrentsProduct("currents_predictions") == "currents_predictions"

    def test_invalid_currents_product_raises(self):
        """An invalid currents product should raise ValueError."""
        with pytest.raises(ValueError):
            CurrentsProduct("tidal_currents")

    def test_currents_product_member_count(self):
        """CurrentsProduct should have exactly 2 members."""
        assert len(CurrentsProduct) == 2


class TestEnumStringBehavior:
    """Tests verifying str enum behavior shared across all models."""

    def test_datum_is_string(self):
        """Datum members should behave as plain strings."""
        assert isinstance(Datum.MLLW, str)
        assert Datum.MLLW == "MLLW"
        assert f"{Datum.MLLW}" == "Datum.MLLW" or str(Datum.MLLW) == "MLLW"

    def test_units_is_string(self):
        """Units members should behave as plain strings."""
        assert isinstance(Units.METRIC, str)
        assert Units.METRIC == "metric"

    def test_case_sensitivity(self):
        """Enum construction should be case-sensitive."""
        with pytest.raises(ValueError):
            Datum("mllw")
        with pytest.raises(ValueError):
            Units("METRIC")
