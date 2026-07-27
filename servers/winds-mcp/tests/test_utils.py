"""Tests for utility functions: unit conversion, compass direction, CSV parsing."""

import json

from winds_mcp.models import (
    degrees_to_compass,
    ms_to_knots,
    celsius_to_fahrenheit,
    pa_to_inhg,
    m_to_miles,
    kmh_to_knots,
)
from winds_mcp.client import WindsClient


class TestDegreesToCompass:
    """Tests for the degrees_to_compass helper."""

    def test_north(self):
        """0 degrees should be N."""
        assert degrees_to_compass(0) == "N"

    def test_east(self):
        """90 degrees should be E."""
        assert degrees_to_compass(90) == "E"

    def test_south(self):
        """180 degrees should be S."""
        assert degrees_to_compass(180) == "S"

    def test_west(self):
        """270 degrees should be W."""
        assert degrees_to_compass(270) == "W"

    def test_northeast(self):
        """45 degrees should be NE."""
        assert degrees_to_compass(45) == "NE"

    def test_360_wraps_to_north(self):
        """360 degrees should wrap to N."""
        assert degrees_to_compass(360) == "N"

    def test_none_returns_dashes(self):
        """None input should return '---'."""
        assert degrees_to_compass(None) == "---"

    def test_southwest(self):
        """225 degrees should be SW."""
        assert degrees_to_compass(225) == "SW"


class TestUnitConversions:
    """Tests for unit conversion functions."""

    def test_ms_to_knots(self):
        """1 m/s should be approximately 1.94 knots."""
        result = ms_to_knots(1.0)
        assert abs(result - 1.94384) < 0.001

    def test_ms_to_knots_zero(self):
        """0 m/s should be 0 knots."""
        assert ms_to_knots(0.0) == 0.0

    def test_celsius_to_fahrenheit_freezing(self):
        """0°C should be 32°F."""
        assert celsius_to_fahrenheit(0.0) == 32.0

    def test_celsius_to_fahrenheit_boiling(self):
        """100°C should be 212°F."""
        assert celsius_to_fahrenheit(100.0) == 212.0

    def test_celsius_to_fahrenheit_negative(self):
        """-40°C should be -40°F."""
        assert celsius_to_fahrenheit(-40.0) == -40.0

    def test_pa_to_inhg(self):
        """101325 Pa (1 atm) should be approximately 29.92 inHg."""
        result = pa_to_inhg(101325.0)
        assert abs(result - 29.92) < 0.01

    def test_m_to_miles(self):
        """1609.34 m should be approximately 1 mile."""
        result = m_to_miles(1609.34)
        assert abs(result - 1.0) < 0.001

    def test_kmh_to_knots(self):
        """1 km/h should be approximately 0.54 knots."""
        result = kmh_to_knots(1.0)
        assert abs(result - 0.539957) < 0.001


class TestIEMCSVParsing:
    """Tests for IEM CSV response parsing."""

    def test_parse_simple_csv(self):
        """Parse a simple IEM CSV response."""
        csv_text = (
            "station,valid,drct,sknt,gust\n"
            "JFK,2025-01-01 00:00,90.00,14.00,M\n"
            "JFK,2025-01-01 01:00,90.00,17.00,26.00\n"
        )
        result = WindsClient._parse_iem_csv(csv_text)
        assert len(result["results"]) == 2
        assert result["results"][0]["station"] == "JFK"
        assert result["results"][0]["sknt"] == "14.00"

    def test_parse_csv_with_debug_lines(self):
        """Parse CSV with leading # debug lines."""
        csv_text = (
            "#DEBUG: Format Typ    -> onlycomma\n"
            "#DEBUG: Time Period   -> 2025-01-01\n"
            "station,valid,drct,sknt\n"
            "JFK,2025-01-01 00:00,90.00,14.00\n"
        )
        result = WindsClient._parse_iem_csv(csv_text)
        assert len(result["results"]) == 1
        assert result["results"][0]["drct"] == "90.00"

    def test_parse_empty_csv(self):
        """Parse empty response."""
        result = WindsClient._parse_iem_csv("")
        assert result["results"] == []

    def test_parse_header_only(self):
        """Parse CSV with header only (no data rows)."""
        csv_text = "station,valid,drct,sknt\n"
        result = WindsClient._parse_iem_csv(csv_text)
        assert result["results"] == []

    def test_malformed_body_without_station_column_raises(self):
        """A degraded IEM backend can return a 200 with an HTML/error body
        instead of CSV; that has no 'station' column, which is the
        server's own semantic error (WindsAPIError), not a silent empty
        result or garbage rows."""
        import pytest

        from winds_mcp.client import WindsAPIError

        with pytest.raises(WindsAPIError):
            WindsClient._parse_iem_csv("<html>Service Unavailable</html>")


class TestWrapJson:
    """Tests for the shared JSON response wrapper (utils.wrap_json) used by
    every JSON-emitting tool in this server."""

    def test_single_object_envelope(self):
        """A payload with list_key=None is never truncated and reports
        returned=total=1."""
        from winds_mcp.utils import wrap_json

        result = wrap_json({"foo": "bar"}, list_key=None, station_id="KJFK")
        parsed = json.loads(result)

        assert parsed["truncated"] is False
        assert parsed["returned"] == 1
        assert parsed["total"] == 1
        assert parsed["station_id"] == "KJFK"
        assert parsed["data"] == {"foo": "bar"}
        assert "retrieved_at" in parsed
        assert "hint" not in parsed

    def test_head_keep_truncates_to_first_n(self):
        """keep='head' keeps the first max_records items."""
        from winds_mcp.utils import wrap_json

        data = {"features": list(range(10))}
        result = wrap_json(data, list_key="features", max_records=3, keep="head")
        parsed = json.loads(result)

        assert parsed["truncated"] is True
        assert parsed["returned"] == 3
        assert parsed["total"] == 10
        assert parsed["data"]["features"] == [0, 1, 2]
        assert "hint" in parsed

    def test_tail_keep_truncates_to_last_n(self):
        """keep='tail' keeps the last max_records items (the most recent
        end of an oldest-first series)."""
        from winds_mcp.utils import wrap_json

        data = {"results": list(range(10))}
        result = wrap_json(data, list_key="results", max_records=3, keep="tail")
        parsed = json.loads(result)

        assert parsed["truncated"] is True
        assert parsed["returned"] == 3
        assert parsed["total"] == 10
        assert parsed["data"]["results"] == [7, 8, 9]

    def test_under_cap_is_not_truncated(self):
        """A list at or under max_records is left untouched."""
        from winds_mcp.utils import wrap_json

        data = {"results": [1, 2]}
        result = wrap_json(data, list_key="results", max_records=5, keep="tail")
        parsed = json.loads(result)

        assert parsed["truncated"] is False
        assert parsed["returned"] == 2
        assert parsed["total"] == 2
        assert "hint" not in parsed

    def test_hint_wording_reflects_recent_flag(self):
        """recent=True labels the kept slice 'most recent'; recent=False
        (order-unspecified lists, e.g. station listings) labels it 'first'."""
        from winds_mcp.utils import wrap_json

        recent_result = json.loads(
            wrap_json(
                {"results": list(range(5))},
                list_key="results",
                max_records=2,
                keep="tail",
                recent=True,
            )
        )
        unspecified_result = json.loads(
            wrap_json(
                {"features": list(range(5))},
                list_key="features",
                max_records=2,
                keep="head",
                recent=False,
            )
        )

        assert "most recent" in recent_result["hint"]
        assert "first" in unspecified_result["hint"]
