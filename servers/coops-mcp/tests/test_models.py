"""Tests for Pydantic models / enums."""

from coops_mcp.models import (
    CurrentsProduct,
    Datum,
    DateShorthand,
    Interval,
    MetProduct,
    StationType,
    TimeZone,
    Units,
)


class TestEnumValues:
    def test_datum_values(self):
        assert Datum.MLLW.value == "MLLW"
        assert Datum.NAVD.value == "NAVD"
        assert len(Datum) == 10

    def test_units_values(self):
        assert Units.METRIC.value == "metric"
        assert Units.ENGLISH.value == "english"

    def test_timezone_values(self):
        assert TimeZone.GMT.value == "gmt"
        assert TimeZone.LST.value == "lst"
        assert TimeZone.LST_LDT.value == "lst_ldt"

    def test_interval_values(self):
        assert Interval.SIX_MIN.value == "6"
        assert Interval.HOURLY.value == "h"
        assert Interval.HILO.value == "hilo"

    def test_date_shorthand(self):
        assert DateShorthand.TODAY.value == "today"
        assert DateShorthand.LATEST.value == "latest"
        assert DateShorthand.RECENT.value == "recent"

    def test_station_type(self):
        assert StationType.WATERLEVELS.value == "waterlevels"
        assert StationType.CURRENTPREDICTIONS.value == "currentpredictions"

    def test_met_product_values(self):
        assert MetProduct.WIND.value == "wind"
        assert MetProduct.AIR_TEMPERATURE.value == "air_temperature"
        assert len(MetProduct) == 9

    def test_currents_product_values(self):
        assert CurrentsProduct.CURRENTS.value == "currents"
        assert CurrentsProduct.CURRENTS_PREDICTIONS.value == "currents_predictions"

    def test_datum_from_string(self):
        assert Datum("MLLW") == Datum.MLLW
        assert Units("metric") == Units.METRIC

    def test_station_type_from_string(self):
        assert StationType("waterlevels") == StationType.WATERLEVELS
