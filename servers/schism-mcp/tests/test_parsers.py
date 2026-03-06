"""Unit tests for SCHISM input file parsers.

Tests cover param.nml, hgrid.gr3, vgrid.in, and bctides.in parsing.
All tests use local fixture files — no network access required.
"""

from pathlib import Path

from schism_mcp.utils import (
    match_error_pattern,
    parse_bctides,
    parse_hgrid_header,
    parse_param_nml,
    parse_vgrid,
    validate_param_nml,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    """Load a text fixture file."""
    return (FIXTURES_DIR / name).read_text()


class TestParseParamNml:
    """Tests for the param.nml parser."""

    def test_parse_minimal_nml(self) -> None:
        """Parse a minimal param.nml and verify key parameters."""
        text = _load_fixture("param_nml_minimal.txt")
        result = parse_param_nml(text)

        assert result["dt"] == 100.0
        assert result["rnday"] == 30.0
        assert result["ihfskip"] == 864
        assert result["nhot"] == 0

    def test_parse_sections(self) -> None:
        """Verify parameters are organized by section."""
        text = _load_fixture("param_nml_minimal.txt")
        result = parse_param_nml(text)

        sections = result["_sections"]
        assert "CORE" in sections
        assert "OPT" in sections
        assert "SCHOUT" in sections

    def test_parse_core_params(self) -> None:
        """Verify CORE section parameters."""
        text = _load_fixture("param_nml_minimal.txt")
        result = parse_param_nml(text)

        assert result["_sections"]["CORE"]["dt"] == 100.0
        assert result["_sections"]["CORE"]["nhot_write"] == 1

    def test_parse_opt_params(self) -> None:
        """Verify OPT section parameters."""
        text = _load_fixture("param_nml_minimal.txt")
        result = parse_param_nml(text)

        assert result["ics"] == 2
        assert result["nws"] == 2
        assert result["h0"] == 0.01
        assert result["slam0"] == -75.0
        assert result["sfea0"] == 38.0

    def test_parse_schout_params(self) -> None:
        """Verify SCHOUT section parameters."""
        text = _load_fixture("param_nml_minimal.txt")
        result = parse_param_nml(text)

        assert result["nspool"] == 36
        assert result["iof_hydro(1)"] == 1

    def test_parse_comments_stripped(self) -> None:
        """Inline comments are stripped from values."""
        text = _load_fixture("param_nml_minimal.txt")
        result = parse_param_nml(text)

        # dt = 100.0 ! timestep in seconds — value should be 100.0, not include comment
        assert isinstance(result["dt"], float)

    def test_parse_empty_text(self) -> None:
        """Parser handles empty input."""
        result = parse_param_nml("")
        assert "_sections" in result

    def test_parse_boolean_values(self) -> None:
        """Parser handles FORTRAN boolean values."""
        text = "&TEST\nflag1 = .true.\nflag2 = .false.\n/"
        result = parse_param_nml(text)
        assert result["flag1"] is True
        assert result["flag2"] is False

    def test_parse_quoted_string(self) -> None:
        """Parser handles quoted string values."""
        text = "&TEST\nname = 'test run'\n/"
        result = parse_param_nml(text)
        assert result["name"] == "test run"


class TestParseHgridHeader:
    """Tests for the hgrid.gr3 header parser."""

    def test_parse_header(self) -> None:
        """Parse hgrid header and verify counts."""
        text = _load_fixture("hgrid_header.txt")
        result = parse_hgrid_header(text)

        assert result["grid_name"] == "Chesapeake Bay Test Grid"
        assert result["num_elements"] == 2000
        assert result["num_nodes"] == 1100

    def test_parse_bounding_box(self) -> None:
        """Verify bounding box is computed from available nodes."""
        text = _load_fixture("hgrid_header.txt")
        result = parse_hgrid_header(text)

        assert "bounding_box" in result
        bb = result["bounding_box"]
        assert bb["min_x"] < bb["max_x"]
        assert bb["min_y"] < bb["max_y"]

    def test_parse_max_depth(self) -> None:
        """Verify max depth is computed."""
        text = _load_fixture("hgrid_header.txt")
        result = parse_hgrid_header(text)

        assert result.get("max_depth", 0) > 0

    def test_parse_short_file(self) -> None:
        """Parser handles files that are too short."""
        result = parse_hgrid_header("only one line")
        assert "error" in result


class TestParseVgrid:
    """Tests for the vgrid.in parser."""

    def test_parse_sz_grid(self) -> None:
        """Parse an SZ-type vertical grid."""
        text = _load_fixture("vgrid_sample.txt")
        result = parse_vgrid(text)

        assert result["ivcor"] == 2
        assert result["type_name"] == "SZ"
        assert result["nvrt"] == 20

    def test_parse_kz_and_hs(self) -> None:
        """Verify Z-level count and transition depth for SZ grid."""
        text = _load_fixture("vgrid_sample.txt")
        result = parse_vgrid(text)

        assert result["kz"] == 5
        assert result["h_s"] == 50.0

    def test_parse_empty_file(self) -> None:
        """Parser handles empty input."""
        result = parse_vgrid("")
        assert "error" in result


class TestParseBctides:
    """Tests for the bctides.in parser."""

    def test_parse_constituents(self) -> None:
        """Parse bctides and verify constituent list."""
        text = _load_fixture("bctides_sample.txt")
        result = parse_bctides(text)

        assert result["nbfr"] == 3
        assert len(result["constituents"]) == 3
        names = [c["name"] for c in result["constituents"]]
        assert "M2" in names
        assert "S2" in names
        assert "K1" in names

    def test_parse_boundaries(self) -> None:
        """Parse boundary segment information."""
        text = _load_fixture("bctides_sample.txt")
        result = parse_bctides(text)

        assert result.get("num_open_boundaries") == 2

    def test_parse_short_file(self) -> None:
        """Parser handles files that are too short."""
        result = parse_bctides("just one line")
        assert "error" in result


class TestValidateParamNml:
    """Tests for param.nml validation."""

    def test_validate_good_config(self) -> None:
        """Good configuration produces no errors."""
        text = _load_fixture("param_nml_minimal.txt")
        parsed = parse_param_nml(text)
        issues = validate_param_nml(parsed)

        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) == 0

    def test_validate_bad_config(self) -> None:
        """Bad configuration detects issues."""
        text = _load_fixture("param_nml_errors.txt")
        parsed = parse_param_nml(text)
        issues = validate_param_nml(parsed)

        errors = [i for i in issues if i["severity"] == "error"]
        assert len(errors) > 0

    def test_validate_nspool_divisibility(self) -> None:
        """Detect nspool/ihfskip divisibility issue."""
        parsed = {"nspool": 7, "ihfskip": 100}
        issues = validate_param_nml(parsed)

        assert any("nspool" in i["parameter"] for i in issues)

    def test_validate_negative_dt(self) -> None:
        """Detect negative timestep."""
        parsed = {"dt": -100.0}
        issues = validate_param_nml(parsed)

        assert any(i["severity"] == "error" and "dt" in i["parameter"] for i in issues)


class TestMatchErrorPattern:
    """Tests for the error pattern matcher."""

    def test_match_nan_error(self) -> None:
        """Match NaN divergence error."""
        matches = match_error_pattern(
            "Solution diverged with NaN values at timestep 500"
        )
        assert len(matches) > 0
        assert any("divergence" in m["diagnosis"].lower() for m in matches)

    def test_match_sflux_error(self) -> None:
        """Match sflux atmospheric forcing error."""
        matches = match_error_pattern("Cannot read sflux_air_1 file for wind forcing")
        assert len(matches) > 0
        assert any(
            "atmospheric" in m["diagnosis"].lower() or "sflux" in m["diagnosis"].lower()
            for m in matches
        )

    def test_match_hotstart_error(self) -> None:
        """Match hotstart error."""
        matches = match_error_pattern("Hotstart.nc file incompatible with current grid")
        assert len(matches) > 0

    def test_no_match(self) -> None:
        """No match for unrelated text."""
        matches = match_error_pattern("Everything is working perfectly fine")
        assert len(matches) == 0
