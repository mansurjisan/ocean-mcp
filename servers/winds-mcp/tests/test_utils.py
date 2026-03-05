"""Tests for utility functions: unit conversion, compass direction, CSV parsing."""

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
