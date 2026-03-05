"""Validation tests for winds-mcp models and input constraints."""

import pytest

from winds_mcp.models import Units, US_STATES


class TestUnits:
    """Tests for the Units enum."""

    def test_valid_metric(self):
        """Metric should be constructible."""
        assert Units("metric") == "metric"

    def test_valid_english(self):
        """English should be constructible."""
        assert Units("english") == "english"

    def test_invalid_units_raises(self):
        """An invalid unit string should raise ValueError."""
        with pytest.raises(ValueError):
            Units("imperial")

    def test_units_member_count(self):
        """Units should have exactly 2 members."""
        assert len(Units) == 2

    def test_case_sensitivity(self):
        """Enum construction should be case-sensitive."""
        with pytest.raises(ValueError):
            Units("METRIC")

    def test_units_is_string(self):
        """Units members should behave as plain strings."""
        assert isinstance(Units.METRIC, str)
        assert Units.METRIC == "metric"


class TestUSStates:
    """Tests for US state code validation."""

    def test_all_50_states_plus_territories(self):
        """US_STATES should contain all 50 states plus territories."""
        assert len(US_STATES) >= 50
        assert "NY" in US_STATES
        assert "CA" in US_STATES
        assert "TX" in US_STATES

    def test_state_names(self):
        """State names should be full names."""
        assert US_STATES["NY"] == "New York"
        assert US_STATES["CA"] == "California"
        assert US_STATES["FL"] == "Florida"

    def test_territories_included(self):
        """DC and territories should be included."""
        assert "DC" in US_STATES
        assert "PR" in US_STATES
        assert "GU" in US_STATES

    def test_invalid_state_not_present(self):
        """Invalid state codes should not be in the dict."""
        assert "XX" not in US_STATES
        assert "ZZ" not in US_STATES
        assert "" not in US_STATES


class TestStationIdFormat:
    """Tests verifying station ID handling patterns."""

    def test_icao_code_uppercase(self):
        """ICAO station IDs should be uppercase."""
        station_id = "kjfk"
        assert station_id.upper() == "KJFK"

    def test_k_prefix_stripping(self):
        """K prefix stripping for IEM FAA codes."""
        station_id = "KJFK"
        if len(station_id) == 4 and station_id.startswith("K"):
            faa_code = station_id[1:]
        else:
            faa_code = station_id
        assert faa_code == "JFK"

    def test_three_char_no_strip(self):
        """3-char codes should not be stripped."""
        station_id = "JFK"
        if len(station_id) == 4 and station_id.startswith("K"):
            faa_code = station_id[1:]
        else:
            faa_code = station_id
        assert faa_code == "JFK"

    def test_non_k_four_char_no_strip(self):
        """4-char codes not starting with K should not be stripped."""
        station_id = "PAFA"  # Fairbanks, AK
        if len(station_id) == 4 and station_id.startswith("K"):
            faa_code = station_id[1:]
        else:
            faa_code = station_id
        assert faa_code == "PAFA"


class TestDateValidation:
    """Tests for date format validation patterns used in tools."""

    def test_valid_date_format(self):
        """YYYY-MM-DD should parse correctly."""
        from datetime import datetime

        dt = datetime.strptime("2025-01-15", "%Y-%m-%d")
        assert dt.year == 2025
        assert dt.month == 1
        assert dt.day == 15

    def test_invalid_date_format_raises(self):
        """Non-YYYY-MM-DD format should raise ValueError."""
        from datetime import datetime

        with pytest.raises(ValueError):
            datetime.strptime("01-15-2025", "%Y-%m-%d")

    def test_date_range_calculation(self):
        """Date range delta should be computed correctly."""
        from datetime import datetime

        start = datetime.strptime("2025-01-01", "%Y-%m-%d")
        end = datetime.strptime("2025-12-31", "%Y-%m-%d")
        delta = (end - start).days
        assert delta == 364

    def test_end_before_start_detected(self):
        """End date before start date should be detectable."""
        from datetime import datetime

        start = datetime.strptime("2025-06-01", "%Y-%m-%d")
        end = datetime.strptime("2025-01-01", "%Y-%m-%d")
        assert end < start
