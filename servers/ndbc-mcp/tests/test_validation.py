"""Validation tests for NDBC models, enums, parsers, and helpers."""

import pytest

from ndbc_mcp.models import (
    COLUMN_LABELS,
    MISSING_VALUES,
    STANDARD_COLUMNS,
    SUMMARY_VARIABLES,
    DataFile,
    StationType,
    degrees_to_compass,
    ms_to_knots,
    celsius_to_fahrenheit,
    hpa_to_inhg,
    m_to_ft,
)
from ndbc_mcp.client import (
    _parse_active_stations_xml,
    parse_realtime_text,
    haversine_distance,
)


class TestStationType:
    """Tests for the StationType enum."""

    def test_valid_types(self):
        """All defined station types should be constructible."""
        for val in ("buoy", "fixed", "other", "dart", "oilrig", "tides", "cman"):
            assert StationType(val).value == val

    def test_invalid_type_raises(self):
        """An invalid station type should raise ValueError."""
        with pytest.raises(ValueError):
            StationType("submarine")

    def test_member_count(self):
        """StationType should have exactly 7 members."""
        assert len(StationType) == 7


class TestDataFile:
    """Tests for the DataFile enum."""

    def test_valid_extensions(self):
        """All data file extensions should be constructible."""
        for val in ("txt", "spec", "drift", "cwind", "ocean"):
            assert DataFile(val).value == val

    def test_invalid_extension_raises(self):
        """An invalid file extension should raise ValueError."""
        with pytest.raises(ValueError):
            DataFile("csv")


class TestDegreesToCompass:
    """Tests for the degrees_to_compass helper."""

    def test_north(self):
        """0 degrees should be N."""
        assert degrees_to_compass(0.0) == "N"

    def test_east(self):
        """90 degrees should be E."""
        assert degrees_to_compass(90.0) == "E"

    def test_south(self):
        """180 degrees should be S."""
        assert degrees_to_compass(180.0) == "S"

    def test_west(self):
        """270 degrees should be W."""
        assert degrees_to_compass(270.0) == "W"

    def test_360_wraps_to_north(self):
        """360 degrees should wrap to N."""
        assert degrees_to_compass(360.0) == "N"

    def test_none_returns_dashes(self):
        """None input should return '---'."""
        assert degrees_to_compass(None) == "---"


class TestUnitConverters:
    """Tests for unit conversion functions."""

    def test_ms_to_knots(self):
        """1 m/s should be approximately 1.944 knots."""
        assert abs(ms_to_knots(1.0) - 1.94384) < 0.001

    def test_celsius_to_fahrenheit(self):
        """0 C should be 32 F."""
        assert abs(celsius_to_fahrenheit(0.0) - 32.0) < 0.01

    def test_celsius_to_fahrenheit_100(self):
        """100 C should be 212 F."""
        assert abs(celsius_to_fahrenheit(100.0) - 212.0) < 0.01

    def test_hpa_to_inhg(self):
        """1013.25 hPa should be approximately 29.92 inHg."""
        assert abs(hpa_to_inhg(1013.25) - 29.92) < 0.01

    def test_m_to_ft(self):
        """1 metre should be approximately 3.281 feet."""
        assert abs(m_to_ft(1.0) - 3.28084) < 0.001


class TestParseRealtimeText:
    """Tests for the realtime2 text parser."""

    SAMPLE_TEXT = """\
#YY  MM DD hh mm WDIR WSPD GST  WVHT   DPD   APD MWD   PRES  ATMP  WTMP  DEWP  VIS PTDY  TIDE
#yr  mo dy hr mn degT m/s  m/s     m   sec   sec degT   hPa  degC  degC  degC  nmi  hPa    ft
2026 03 07 11 30 160  2.0  3.0    MM    MM    MM  MM 1025.4   2.3   2.4   2.2   MM   MM    MM
2026 03 07 11 20 170  1.0  2.0   1.9     8   6.5 100 1025.5   2.3   2.4   2.2   MM   MM    MM
"""

    def test_returns_columns_and_records(self):
        """Parser should return column names and records."""
        columns, records = parse_realtime_text(self.SAMPLE_TEXT)
        assert "WDIR" in columns
        assert "WSPD" in columns
        assert len(records) == 2

    def test_datetime_parsed(self):
        """Records should have a datetime field."""
        _, records = parse_realtime_text(self.SAMPLE_TEXT)
        dt = records[0]["datetime"]
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 7
        assert dt.hour == 11
        assert dt.minute == 30

    def test_missing_values_are_none(self):
        """MM values should be parsed as None."""
        _, records = parse_realtime_text(self.SAMPLE_TEXT)
        assert records[0]["WVHT"] is None
        assert records[0]["DPD"] is None

    def test_numeric_values_are_float(self):
        """Numeric values should be parsed as float."""
        _, records = parse_realtime_text(self.SAMPLE_TEXT)
        assert records[0]["WSPD"] == 2.0
        assert records[0]["PRES"] == 1025.4

    def test_empty_text_returns_empty(self):
        """Empty input should return empty lists."""
        columns, records = parse_realtime_text("")
        assert columns == []
        assert records == []


class TestParseActiveStationsXml:
    """Tests for the active stations XML parser."""

    SAMPLE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<stations created="2026-03-07T11:55:02UTC" count="2">
  <station id="44013" lat="42.346" lon="-70.651" name="Boston" owner="NDBC" pgm="NDBC" type="buoy" met="y" currents="n" waterquality="n" dart="n"/>
  <station id="21413" lat="30.487" lon="152.124" name="SE Tokyo" owner="NDBC" pgm="Tsunami" type="dart" met="n" currents="n" waterquality="n" dart="y"/>
</stations>
"""

    def test_parses_stations(self):
        """Parser should return a list of station dicts."""
        stations = _parse_active_stations_xml(self.SAMPLE_XML)
        assert len(stations) == 2

    def test_station_fields(self):
        """Each station should have standard fields."""
        stations = _parse_active_stations_xml(self.SAMPLE_XML)
        s = stations[0]
        assert s["id"] == "44013"
        assert s["lat"] == 42.346
        assert s["lon"] == -70.651
        assert s["type"] == "buoy"
        assert s["met"] == "y"

    def test_station_id_uppercased(self):
        """Station IDs should be uppercased."""
        stations = _parse_active_stations_xml(self.SAMPLE_XML)
        for s in stations:
            assert s["id"] == s["id"].upper()


class TestHaversineDistance:
    """Tests for the haversine distance function."""

    def test_same_point(self):
        """Distance between the same point should be 0."""
        assert haversine_distance(40.0, -74.0, 40.0, -74.0) == 0.0

    def test_known_distance(self):
        """NYC to London should be ~5570 km."""
        dist = haversine_distance(40.7128, -74.0060, 51.5074, -0.1278)
        assert 5500 < dist < 5650

    def test_symmetry(self):
        """Distance should be symmetric."""
        d1 = haversine_distance(40.0, -74.0, 42.0, -71.0)
        d2 = haversine_distance(42.0, -71.0, 40.0, -74.0)
        assert abs(d1 - d2) < 0.001


class TestConstants:
    """Tests for model constants and column definitions."""

    def test_standard_columns_count(self):
        """Standard columns should have 19 entries (5 datetime + 14 data)."""
        assert len(STANDARD_COLUMNS) == 19

    def test_all_data_columns_have_labels(self):
        """Every data column should have a label."""
        for col in STANDARD_COLUMNS[5:]:
            assert col in COLUMN_LABELS, f"Missing label for {col}"

    def test_summary_variables_subset(self):
        """Summary variables should be a subset of standard data columns."""
        data_cols = set(STANDARD_COLUMNS[5:])
        for v in SUMMARY_VARIABLES:
            assert v in data_cols, f"{v} not in standard columns"

    def test_missing_values_set(self):
        """MM should be in the missing values set."""
        assert "MM" in MISSING_VALUES
        assert "999.0" in MISSING_VALUES
