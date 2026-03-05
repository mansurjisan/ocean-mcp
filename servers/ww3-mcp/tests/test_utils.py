"""Unit tests for ww3_mcp.utils — parsers, helpers, and formatters."""

from __future__ import annotations

from pathlib import Path

from ww3_mcp.utils import (
    denormalize_lon,
    format_wave_observation_table,
    haversine,
    normalize_lon,
    parse_ndbc_realtime,
    parse_ndbc_stations_xml,
    compute_validation_stats,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ============================================================================
# Haversine
# ============================================================================


class TestHaversine:
    """Tests for the haversine distance function."""

    def test_same_point_returns_zero(self):
        """Haversine distance between identical points should be zero."""
        assert haversine(40.0, -74.0, 40.0, -74.0) == 0.0

    def test_known_distance_nyc_to_london(self):
        """NYC to London should be approximately 5570 km."""
        dist = haversine(40.7128, -74.0060, 51.5074, -0.1278)
        assert 5550 < dist < 5600

    def test_equator_one_degree(self):
        """One degree of longitude on the equator is about 111 km."""
        dist = haversine(0.0, 0.0, 0.0, 1.0)
        assert 110 < dist < 112

    def test_symmetry(self):
        """Haversine should be symmetric."""
        d1 = haversine(35.0, -75.0, 40.0, -74.0)
        d2 = haversine(40.0, -74.0, 35.0, -75.0)
        assert abs(d1 - d2) < 0.001


# ============================================================================
# Longitude normalization
# ============================================================================


class TestLonNormalization:
    """Tests for longitude conversion between -180..180 and 0..360."""

    def test_normalize_negative_longitude(self):
        """Negative longitude should be converted to 0-360 range."""
        assert normalize_lon(-75.0) == 285.0

    def test_normalize_positive_longitude(self):
        """Positive longitude in 0-180 range should stay the same."""
        assert normalize_lon(120.0) == 120.0

    def test_normalize_zero(self):
        """Zero longitude should stay zero."""
        assert normalize_lon(0.0) == 0.0

    def test_normalize_minus_180(self):
        """Longitude -180 should become 180."""
        assert normalize_lon(-180.0) == 180.0

    def test_denormalize_above_180(self):
        """Longitude above 180 in 0-360 should be converted to negative."""
        assert denormalize_lon(285.0) == -75.0

    def test_denormalize_below_180(self):
        """Longitude below 180 should stay the same."""
        assert denormalize_lon(120.0) == 120.0

    def test_roundtrip(self):
        """Normalize then denormalize should return the original value."""
        original = -75.5
        assert abs(denormalize_lon(normalize_lon(original)) - original) < 0.001


# ============================================================================
# NDBC realtime text parser
# ============================================================================


class TestParseNdbcRealtime:
    """Tests for NDBC realtime2 text file parsing."""

    def test_parse_fixture_file(self):
        """Parsing the fixture file should return 5 records."""
        text = (FIXTURES_DIR / "ndbc_realtime.txt").read_text()
        records = parse_ndbc_realtime(text)
        assert len(records) == 5

    def test_parse_extracts_wave_height(self):
        """Each record should have a numeric WVHT field."""
        text = (FIXTURES_DIR / "ndbc_realtime.txt").read_text()
        records = parse_ndbc_realtime(text)
        for r in records:
            assert r["WVHT"] is not None
            assert isinstance(r["WVHT"], float)

    def test_parse_missing_values_become_none(self):
        """Values of 'MM' in NDBC data should become None."""
        text = (FIXTURES_DIR / "ndbc_realtime.txt").read_text()
        records = parse_ndbc_realtime(text)
        # VIS, PTDY, TIDE are all MM in fixture
        for r in records:
            assert r.get("VIS") is None
            assert r.get("PTDY") is None

    def test_parse_builds_timestamps(self):
        """Parser should create timestamp strings from date components."""
        text = (FIXTURES_DIR / "ndbc_realtime.txt").read_text()
        records = parse_ndbc_realtime(text)
        assert records[0]["timestamp"] == "2026-03-04 12:00"

    def test_parse_empty_text_returns_empty(self):
        """Parsing empty text should return an empty list."""
        assert parse_ndbc_realtime("") == []

    def test_parse_header_only_returns_empty(self):
        """Parsing text with only headers and no data should return empty."""
        text = "#YY  MM DD hh mm WDIR\n#yr  mo dy hr mn deg\n"
        assert parse_ndbc_realtime(text) == []


# ============================================================================
# NDBC stations XML parser
# ============================================================================


class TestParseNdbcStationsXml:
    """Tests for NDBC active stations XML parsing."""

    def test_parse_fixture_file(self):
        """Parsing the fixture XML should return 5 stations."""
        xml = (FIXTURES_DIR / "ndbc_stations.xml").read_text()
        stations = parse_ndbc_stations_xml(xml)
        assert len(stations) == 5

    def test_parse_extracts_station_ids(self):
        """Each station should have an 'id' field."""
        xml = (FIXTURES_DIR / "ndbc_stations.xml").read_text()
        stations = parse_ndbc_stations_xml(xml)
        ids = {s["id"] for s in stations}
        assert "41025" in ids
        assert "46042" in ids

    def test_parse_extracts_coordinates(self):
        """Each station should have numeric lat/lon fields."""
        xml = (FIXTURES_DIR / "ndbc_stations.xml").read_text()
        stations = parse_ndbc_stations_xml(xml)
        for s in stations:
            assert isinstance(s["lat"], float)
            assert isinstance(s["lon"], float)

    def test_parse_invalid_xml_returns_empty(self):
        """Invalid XML should return an empty list."""
        assert parse_ndbc_stations_xml("not xml") == []

    def test_parse_extracts_name(self):
        """Stations should have name attributes."""
        xml = (FIXTURES_DIR / "ndbc_stations.xml").read_text()
        stations = parse_ndbc_stations_xml(xml)
        diamond = next(s for s in stations if s["id"] == "41025")
        assert "Diamond Shoals" in diamond["name"]


# ============================================================================
# Validation statistics
# ============================================================================


class TestComputeValidationStats:
    """Tests for the compute_validation_stats function."""

    def test_perfect_forecast(self):
        """Identical forecast and observed should give zero error metrics."""
        stats = compute_validation_stats([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        assert stats["bias"] == 0.0
        assert stats["rmse"] == 0.0
        assert stats["mae"] == 0.0
        assert stats["n"] == 3

    def test_constant_bias(self):
        """A constant offset should be reflected in bias."""
        stats = compute_validation_stats([2.0, 3.0, 4.0], [1.0, 2.0, 3.0])
        assert abs(stats["bias"] - 1.0) < 0.001

    def test_empty_arrays_return_none(self):
        """Empty input should return None metrics and n=0."""
        stats = compute_validation_stats([], [])
        assert stats["n"] == 0
        assert stats["bias"] is None

    def test_correlation_for_perfect_linear(self):
        """Perfect linear correlation should give R close to 1."""
        stats = compute_validation_stats([2.0, 4.0, 6.0], [1.0, 2.0, 3.0])
        assert stats["correlation"] is not None
        assert stats["correlation"] > 0.99


# ============================================================================
# Formatters
# ============================================================================


class TestFormatWaveObservationTable:
    """Tests for the wave observation table formatter."""

    def test_format_returns_markdown_table(self):
        """Formatter should produce a markdown table with headers."""
        records = [
            {
                "timestamp": "2026-03-04 12:00",
                "WVHT": 1.5,
                "DPD": 8.0,
                "APD": 5.5,
                "MWD": 200,
                "WSPD": 5.1,
                "WDIR": 210,
            },
        ]
        result = format_wave_observation_table(records, station_id="41025")
        assert "| Time (UTC) |" in result
        assert "41025" in result

    def test_format_empty_records(self):
        """Formatter with no records should show a 'no data' message."""
        result = format_wave_observation_table([], station_id="41025")
        assert "No observation data" in result

    def test_format_handles_none_values(self):
        """Formatter should show '—' for None values."""
        records = [
            {
                "timestamp": "2026-03-04 12:00",
                "WVHT": None,
                "DPD": None,
                "APD": None,
                "MWD": None,
                "WSPD": None,
                "WDIR": None,
            },
        ]
        result = format_wave_observation_table(records)
        assert "—" in result
