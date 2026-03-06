"""Tests for models, constants, and RDB parsing in usgs-mcp."""

from usgs_mcp.client import parse_rdb
from usgs_mcp.models import (
    FLOOD_CATEGORIES,
    PARAMETER_CODES,
    QUALIFICATION_CODES,
    REFERENCE_SITES,
    US_STATE_CODES,
    format_parameter,
)


class TestParameterCodes:
    """Tests for USGS parameter code constants."""

    def test_discharge_code_exists(self):
        """Discharge parameter code 00060 is defined."""
        assert "00060" in PARAMETER_CODES
        assert PARAMETER_CODES["00060"]["name"] == "Discharge"

    def test_gage_height_code_exists(self):
        """Gage height parameter code 00065 is defined."""
        assert "00065" in PARAMETER_CODES
        assert PARAMETER_CODES["00065"]["name"] == "Gage height"

    def test_all_codes_have_required_fields(self):
        """All parameter codes have name, units, and description."""
        for code, info in PARAMETER_CODES.items():
            assert "name" in info, f"Code {code} missing 'name'"
            assert "units" in info, f"Code {code} missing 'units'"
            assert "description" in info, f"Code {code} missing 'description'"


class TestReferenceSites:
    """Tests for reference site constants."""

    def test_potomac_site_exists(self):
        """Potomac River reference site is defined."""
        assert "01646500" in REFERENCE_SITES
        assert "Potomac" in REFERENCE_SITES["01646500"]["name"]

    def test_all_sites_have_required_fields(self):
        """All reference sites have name and state."""
        for site_id, info in REFERENCE_SITES.items():
            assert "name" in info, f"Site {site_id} missing 'name'"
            assert "state" in info, f"Site {site_id} missing 'state'"

    def test_site_ids_are_8_digits(self):
        """All reference site IDs are 8-digit strings."""
        for site_id in REFERENCE_SITES:
            assert len(site_id) == 8, f"Site ID {site_id} is not 8 chars"
            assert site_id.isdigit(), f"Site ID {site_id} is not numeric"


class TestStateCodes:
    """Tests for US state code constants."""

    def test_at_least_50_states(self):
        """State codes dict has at least 50 entries."""
        assert len(US_STATE_CODES) >= 50

    def test_common_states_present(self):
        """Common state codes are present."""
        assert "MD" in US_STATE_CODES
        assert "TX" in US_STATE_CODES
        assert "CA" in US_STATE_CODES
        assert "NY" in US_STATE_CODES

    def test_territories_present(self):
        """US territories are included."""
        assert "PR" in US_STATE_CODES
        assert "DC" in US_STATE_CODES

    def test_invalid_codes_absent(self):
        """Invalid state codes are not present."""
        assert "ZZ" not in US_STATE_CODES
        assert "XX" not in US_STATE_CODES
        assert "" not in US_STATE_CODES


class TestQualificationCodes:
    """Tests for USGS data qualification codes."""

    def test_approved_code(self):
        """Approved qualification code is defined."""
        assert "A" in QUALIFICATION_CODES
        assert "Approved" in QUALIFICATION_CODES["A"]

    def test_provisional_code(self):
        """Provisional qualification code is defined."""
        assert "P" in QUALIFICATION_CODES


class TestFloodCategories:
    """Tests for flood category constants."""

    def test_flood_categories_defined(self):
        """Flood categories include action, flood, moderate, major."""
        assert "action" in FLOOD_CATEGORIES
        assert "flood" in FLOOD_CATEGORIES
        assert "moderate" in FLOOD_CATEGORIES
        assert "major" in FLOOD_CATEGORIES


class TestFormatParameter:
    """Tests for format_parameter helper."""

    def test_known_code(self):
        """Known parameter code returns human-readable name."""
        result = format_parameter("00060")
        assert "Discharge" in result
        assert "cfs" in result

    def test_unknown_code(self):
        """Unknown parameter code returns generic label."""
        result = format_parameter("99999")
        assert "Parameter 99999" in result


class TestRDBParser:
    """Tests for USGS RDB tab-delimited format parser."""

    def test_parse_basic_rdb(self):
        """Parse a simple RDB string with comments, header, type row, data."""
        rdb = (
            "# Comment line\n"
            "# Another comment\n"
            "site_no\tstation_nm\tdec_lat_va\n"
            "15s\t50s\t10s\n"
            "01646500\tPotomac River\t38.9\n"
            "07010000\tMississippi River\t38.6\n"
        )
        rows = parse_rdb(rdb)
        assert len(rows) == 2
        assert rows[0]["site_no"] == "01646500"
        assert rows[0]["station_nm"] == "Potomac River"
        assert rows[1]["site_no"] == "07010000"

    def test_parse_empty_rdb(self):
        """Parse empty string returns empty list."""
        assert parse_rdb("") == []

    def test_parse_comments_only(self):
        """Parse RDB with only comment lines returns empty list."""
        rdb = "# Just comments\n# Nothing else\n"
        assert parse_rdb(rdb) == []

    def test_parse_header_only(self):
        """Parse RDB with header and type row but no data returns empty list."""
        rdb = "col1\tcol2\n5s\t10s\n"
        assert parse_rdb(rdb) == []

    def test_parse_skips_blank_lines(self):
        """Parse RDB skips blank data lines."""
        rdb = "col1\tcol2\n5s\t10s\na\tb\n\nc\td\n"
        rows = parse_rdb(rdb)
        assert len(rows) == 2
        assert rows[0]["col1"] == "a"
        assert rows[1]["col1"] == "c"
