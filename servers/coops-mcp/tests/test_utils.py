"""Tests for utility functions."""

import json

import pytest

from coops_mcp.utils import (
    format_json_response,
    format_station_summary,
    format_tabular_data,
    haversine_distance,
    normalize_date,
    validate_date_range,
)


class TestHaversine:
    def test_same_point(self):
        assert haversine_distance(40.0, -74.0, 40.0, -74.0) == 0.0

    def test_known_distance(self):
        # NYC to London is ~5570 km
        dist = haversine_distance(40.7128, -74.0060, 51.5074, -0.1278)
        assert 5550 < dist < 5600

    def test_short_distance(self):
        # ~1 degree of latitude is ~111 km
        dist = haversine_distance(40.0, -74.0, 41.0, -74.0)
        assert 110 < dist < 112

    def test_equator_to_pole(self):
        dist = haversine_distance(0.0, 0.0, 90.0, 0.0)
        assert 10000 < dist < 10020


class TestNormalizeDate:
    def test_already_coops_format(self):
        assert normalize_date("20241001") == "20241001"

    def test_already_coops_with_time(self):
        assert normalize_date("20241001 14:30") == "20241001 14:30"

    def test_iso_date(self):
        assert normalize_date("2024-10-01") == "20241001"

    def test_iso_datetime(self):
        assert normalize_date("2024-10-01T14:30:00") == "20241001 14:30"

    def test_iso_datetime_short(self):
        assert normalize_date("2024-10-01T14:30") == "20241001 14:30"

    def test_slash_date(self):
        assert normalize_date("2024/10/01") == "20241001"

    def test_date_with_spaces(self):
        assert normalize_date("  20241001  ") == "20241001"

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="Unrecognized date format"):
            normalize_date("October 1, 2024")


class TestValidateDateRange:
    def test_valid_range(self):
        validate_date_range("20241001", "20241015")  # 14 days — should pass

    def test_one_year_max(self):
        validate_date_range("20240101", "20241231")  # 365 days

    def test_exceeds_limit(self):
        with pytest.raises(ValueError, match="exceeds the maximum"):
            validate_date_range("20230101", "20241231")  # 730 days

    def test_end_before_begin(self):
        with pytest.raises(ValueError, match="before begin_date"):
            validate_date_range("20241015", "20241001")

    def test_custom_max_days(self):
        validate_date_range("20240101", "20240601", max_days=3650)

    def test_custom_max_days_exceeded(self):
        with pytest.raises(ValueError, match="exceeds the maximum"):
            validate_date_range("20240101", "20350101", max_days=3650)


class TestFormatStationSummary:
    def test_basic_station(self):
        station = {
            "id": "8518750",
            "name": "The Battery",
            "state": "NY",
            "lat": 40.7006,
            "lng": -74.0142,
        }
        result = format_station_summary(station)
        assert "8518750" in result
        assert "The Battery" in result
        assert "NY" in result

    def test_station_without_state(self):
        station = {"id": "1234567", "name": "Some Station", "lat": 20.0, "lng": -160.0}
        result = format_station_summary(station)
        assert "Some Station" in result
        assert ", " not in result.split(" - ")[1].split(" (")[0]  # no trailing comma

    def test_station_alt_keys(self):
        station = {
            "stationId": "9999",
            "name": "Alt",
            "latitude": 30.0,
            "longitude": -80.0,
        }
        result = format_station_summary(station)
        assert "9999" in result


class TestFormatTabularData:
    def test_basic_table(self):
        data = [{"t": "2024-10-01", "v": "1.23"}, {"t": "2024-10-02", "v": "1.45"}]
        columns = [("t", "Time"), ("v", "Value")]
        result = format_tabular_data(data, columns, title="Test")
        assert "## Test" in result
        assert "| Time | Value |" in result
        assert "2024-10-01" in result
        assert "2 records returned" in result

    def test_with_metadata(self):
        result = format_tabular_data([], [("x", "X")], metadata_lines=["Datum: MLLW"])
        assert "**Datum: MLLW**" in result
        assert "0 records returned" in result

    def test_custom_count_label(self):
        result = format_tabular_data(
            [{"a": "1"}], [("a", "A")], count_label="observations"
        )
        assert "1 observations returned" in result

    def test_under_cap_not_truncated(self):
        """At or below max_rows the footer is the plain 'returned' form."""
        data = [{"v": str(i)} for i in range(10)]
        result = format_tabular_data(data, [("v", "V")], max_rows=10)
        assert "10 records returned" in result
        assert "truncated" not in result

    def test_truncates_over_cap_keeping_most_recent(self):
        """Over max_rows, only the most recent rows render and the footer says so."""
        data = [{"v": str(i)} for i in range(2500)]  # 0..2499, oldest first
        result = format_tabular_data(data, [("v", "V")], max_rows=2000)
        assert "Showing the most recent 2000 of 2500 records (truncated)" in result
        # Most recent kept (2499 present), oldest dropped (0 absent as its own row).
        assert "| 2499 |" in result
        assert "| 0 |" not in result


class TestFormatJsonResponse:
    def test_under_cap_untouched(self):
        """A small payload is wrapped but not trimmed; counts agree."""
        data = {"data": [{"v": i} for i in range(5)]}
        parsed = json.loads(format_json_response(data, "8518750", {"product": "x"}))
        assert parsed["station_id"] == "8518750"
        assert parsed["truncated"] is False
        assert parsed["record_count"] == 5
        assert parsed["total_count"] == 5
        assert len(parsed["data"]["data"]) == 5
        assert "hint" not in parsed

    def test_data_shape_capped_keeps_most_recent(self):
        """An over-cap 'data' series is trimmed to its most recent max_records."""
        data = {"data": [{"v": i} for i in range(3000)]}  # 0..2999, oldest first
        parsed = json.loads(format_json_response(data, max_records=2000))
        assert parsed["truncated"] is True
        assert parsed["record_count"] == 2000
        assert parsed["total_count"] == 3000
        kept = parsed["data"]["data"]
        assert len(kept) == 2000
        assert kept[0]["v"] == 1000  # oldest 1000 dropped
        assert kept[-1]["v"] == 2999  # most recent kept
        assert "most recent 2000 of 3000" in parsed["hint"]

    def test_predictions_shape_capped(self):
        """The 'predictions' shape (tide predictions) is capped the same way."""
        data = {"predictions": [{"v": i} for i in range(2500)]}
        parsed = json.loads(format_json_response(data, max_records=2000))
        assert parsed["truncated"] is True
        assert parsed["total_count"] == 2500
        assert len(parsed["data"]["predictions"]) == 2000
        assert parsed["data"]["predictions"][-1]["v"] == 2499

    def test_currents_predictions_nested_cp_capped(self):
        """Currents predictions nest the array at current_predictions.cp."""
        data = {
            "current_predictions": {
                "units": "meters, cm/s",
                "cp": [{"Velocity_Major": i} for i in range(2500)],
            }
        }
        parsed = json.loads(format_json_response(data, max_records=2000))
        assert parsed["truncated"] is True
        assert parsed["total_count"] == 2500
        cp = parsed["data"]["current_predictions"]["cp"]
        assert len(cp) == 2000
        assert cp[-1]["Velocity_Major"] == 2499
        # Sibling metadata is preserved through the cap.
        assert parsed["data"]["current_predictions"]["units"] == "meters, cm/s"
