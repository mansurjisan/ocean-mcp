"""Unit tests for ADCIRC input file parsers.

Tests cover fort.15, fort.14, fort.13, and fort.22 parsing functions.
All tests use local fixture files — no network access required.
"""

from pathlib import Path

from adcirc_mcp.utils import (
    check_cfl,
    match_error_pattern,
    parse_fort13,
    parse_fort14_header,
    parse_fort15,
    parse_fort22_header,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    """Load a text fixture file."""
    return (FIXTURES_DIR / name).read_text()


class TestParseFort15:
    """Tests for the fort.15 parser."""

    def test_parse_minimal_fort15(self) -> None:
        """Parse a minimal but valid fort.15 and verify key parameters."""
        text = _load_fixture("fort15_minimal.txt")
        result = parse_fort15(text)

        assert result["RUNDES"] == "Shinnecock Inlet Coarse Grid - Test Case"
        assert result["RUNID"] == "ShinneTest"
        assert result["IHOT"] == 0
        assert result["ICS"] == 2
        assert result["IM"] == 0
        assert result["DTDP"] == 2.0
        assert result["RNDAY"] == 5.0

    def test_parse_fort15_friction_params(self) -> None:
        """Verify friction parameters are correctly parsed."""
        text = _load_fixture("fort15_minimal.txt")
        result = parse_fort15(text)

        assert result["NOLIBF"] == 1
        assert result["NOLIFA"] == 2
        assert result["CF"] == 0.0025

    def test_parse_fort15_tidal_constituents(self) -> None:
        """Verify tidal potential and boundary forcing constituents are parsed."""
        text = _load_fixture("fort15_minimal.txt")
        result = parse_fort15(text)

        assert result["NTIF"] == 2
        assert len(result["tidal_potential"]) == 2
        assert result["tidal_potential"][0]["name"] == "M2"
        assert result["tidal_potential"][1]["name"] == "S2"

        assert result["NBFR"] == 2
        assert len(result["boundary_forcing"]) == 2
        assert result["boundary_forcing"][0]["name"] == "M2"

    def test_parse_fort15_nodal_attributes(self) -> None:
        """Verify nodal attribute names are parsed correctly."""
        text = _load_fixture("fort15_minimal.txt")
        result = parse_fort15(text)

        assert result["NWP"] == 2
        assert "mannings_n_at_sea_floor" in result["nodal_attributes"]
        assert (
            "primitive_weighting_in_continuity_equation" in result["nodal_attributes"]
        )

    def test_parse_fort15_output_params(self) -> None:
        """Verify output parameters and stations are parsed."""
        text = _load_fixture("fort15_minimal.txt")
        result = parse_fort15(text)

        assert result.get("NOUTE") == 5
        assert result.get("NSTAE") == 3
        assert len(result.get("elevation_stations", [])) == 3

    def test_parse_fort15_spatial_params(self) -> None:
        """Verify spatial projection parameters."""
        text = _load_fixture("fort15_minimal.txt")
        result = parse_fort15(text)

        assert result["SLAM0"] == -73.93
        assert result["SFEA0"] == 40.55
        assert result["TAU0"] == -3.0

    def test_parse_fort15_time_weighting(self) -> None:
        """Verify time weighting factors."""
        text = _load_fixture("fort15_minimal.txt")
        result = parse_fort15(text)

        assert result["A00"] == 0.35
        assert result["B00"] == 0.30
        assert result["C00"] == 0.35

    def test_parse_empty_text(self) -> None:
        """Parser handles empty input gracefully."""
        result = parse_fort15("")
        assert "_raw_lines" in result

    def test_parse_fort15_wetting_drying(self) -> None:
        """Verify wetting/drying parameters."""
        text = _load_fixture("fort15_minimal.txt")
        result = parse_fort15(text)

        assert result["H0"] == 0.05
        assert result.get("NODEDRYMIN") == 0.05
        assert result.get("NODEWETMIN") == 0.1


class TestParseFort14Header:
    """Tests for the fort.14 header parser."""

    def test_parse_header(self) -> None:
        """Parse fort.14 header and verify counts."""
        text = _load_fixture("fort14_header.txt")
        result = parse_fort14_header(text)

        assert result["grid_name"] == "Shinnecock Inlet Coarse Grid"
        assert result["num_elements"] == 1000
        assert result["num_nodes"] == 500

    def test_parse_short_file(self) -> None:
        """Parser handles files that are too short."""
        result = parse_fort14_header("only one line")
        assert "error" in result


class TestParseFort13:
    """Tests for the fort.13 parser."""

    def test_parse_sample(self) -> None:
        """Parse fort.13 and verify attribute definitions."""
        text = _load_fixture("fort13_sample.txt")
        result = parse_fort13(text)

        assert result["num_nodes"] == 500
        assert result["num_attributes"] == 2
        assert len(result["attributes"]) == 2

        assert result["attributes"][0]["name"] == "mannings_n_at_sea_floor"
        assert (
            result["attributes"][1]["name"]
            == "primitive_weighting_in_continuity_equation"
        )

    def test_parse_nondefault_nodes(self) -> None:
        """Verify non-default node counts are parsed."""
        text = _load_fixture("fort13_sample.txt")
        result = parse_fort13(text)

        assert result["attributes"][0]["num_nondefault_nodes"] == 3
        assert result["attributes"][1]["num_nondefault_nodes"] == 2


class TestParseFort22Header:
    """Tests for the fort.22 header parser."""

    def test_parse_atcf_format(self) -> None:
        """Parse ATCF best-track format (NWS=8)."""
        text = _load_fixture("fort22_sample.txt")
        result = parse_fort22_header(text, nws=8)

        assert result["format"] == "ATCF_best_track"
        assert result["num_records"] == 7
        assert "2005082312" in result.get("first_timestamp", "")

    def test_parse_unknown_nws(self) -> None:
        """Parser handles unknown NWS values."""
        result = parse_fort22_header("some data", nws=99)
        assert result["format"] == "unknown"


class TestCheckCFL:
    """Tests for the CFL condition checker."""

    def test_cfl_passes(self) -> None:
        """CFL check passes for reasonable parameters."""
        result = check_cfl(dtdp=2.0, min_edge_length=500.0, max_depth=20.0)
        assert result["passes"] is True
        assert result["cfl_number"] < 1.0

    def test_cfl_fails(self) -> None:
        """CFL check fails for timestep that's too large."""
        result = check_cfl(dtdp=100.0, min_edge_length=50.0, max_depth=100.0)
        assert result["passes"] is False
        assert result["cfl_number"] > 1.0

    def test_cfl_invalid_input(self) -> None:
        """CFL check handles invalid inputs."""
        result = check_cfl(dtdp=1.0, min_edge_length=0, max_depth=10.0)
        assert "error" in result


class TestMatchErrorPattern:
    """Tests for the error pattern matcher."""

    def test_match_cfl_error(self) -> None:
        """Match CFL violation error text."""
        matches = match_error_pattern(
            "Model blew up due to CFL violation at timestep 1000"
        )
        assert len(matches) > 0
        assert any("CFL" in m["diagnosis"] for m in matches)

    def test_match_hotstart_error(self) -> None:
        """Match hot start error text."""
        matches = match_error_pattern("Cannot read fort.67 hot start file")
        assert len(matches) > 0
        assert any("hot start" in m["diagnosis"].lower() for m in matches)

    def test_no_match(self) -> None:
        """No match for unrelated text."""
        matches = match_error_pattern("Everything is working perfectly fine")
        assert len(matches) == 0
