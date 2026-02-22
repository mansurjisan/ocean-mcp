"""Unit tests for recon_mcp.utils parsers — no network access needed."""

import pytest

from recon_mcp.utils import (
    format_tabular_data,
    parse_atcf_fix_record,
    parse_atcf_latlon,
    parse_directory_listing,
    parse_hdob_message,
    parse_vdm_message,
)

# ---------------------------------------------------------------------------
# Directory listing parser
# ---------------------------------------------------------------------------

SAMPLE_DIRECTORY_HTML = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<html><head><title>Index of /archive/recon/2024/AHONT1</title></head>
<body><h1>Index of /archive/recon/2024/AHONT1</h1>
<table>
<tr><th><a href="?C=N;O=D">Name</a></th></tr>
<tr><td><a href="../">Parent Directory</a></td></tr>
<tr><td><a href="AHONT1-KNHC.202410071200.txt">AHONT1-KNHC.202410071200.txt</a></td><td>2024-10-07 12:05</td><td>2.1K</td></tr>
<tr><td><a href="AHONT1-KNHC.202410071230.txt">AHONT1-KNHC.202410071230.txt</a></td><td>2024-10-07 12:35</td><td>1.8K</td></tr>
<tr><td><a href="AHONT1-KNHC.202410071300.txt">AHONT1-KNHC.202410071300.txt</a></td><td>2024-10-07 13:05</td><td>2.3K</td></tr>
</table></body></html>
"""


def test_parse_directory_listing():
    entries = parse_directory_listing(SAMPLE_DIRECTORY_HTML)
    assert len(entries) == 3
    assert entries[0]["filename"] == "AHONT1-KNHC.202410071200.txt"
    assert entries[0]["href"] == "AHONT1-KNHC.202410071200.txt"
    assert entries[2]["filename"] == "AHONT1-KNHC.202410071300.txt"


def test_parse_directory_listing_skips_parent():
    entries = parse_directory_listing(SAMPLE_DIRECTORY_HTML)
    filenames = [e["filename"] for e in entries]
    assert "Parent Directory" not in filenames


def test_parse_directory_listing_empty():
    html = "<html><body>No files</body></html>"
    entries = parse_directory_listing(html)
    assert entries == []


# ---------------------------------------------------------------------------
# HDOB parser
# ---------------------------------------------------------------------------

SAMPLE_HDOB = """URNT15 KNHC 071200
AHONT1
20241007 1200 NOAA2 HDOB 01
20241007 120030 2606N 08015W 7023 03050 0150 +213 +180 270/065 072 055 062 0
20241007 120100 2607N 08016W 7018 03055 0148 +210 +178 268/068 075 058 065 1
20241007 120130 2608N 08017W ///  03060 //// +208 ///  265/070 078 /// 068 0
$$
"""


def test_parse_hdob_message():
    result = parse_hdob_message(SAMPLE_HDOB)
    header = result["header"]
    obs = result["observations"]

    assert header.get("aircraft") == "NOAA2"
    assert header.get("date") == "20241007"
    assert len(obs) == 3


def test_parse_hdob_latlon():
    result = parse_hdob_message(SAMPLE_HDOB)
    obs = result["observations"]

    # 2606N = 26 degrees, 06 minutes = 26.1
    assert obs[0]["lat"] == pytest.approx(26.1, abs=0.01)
    # 08015W = 80 degrees, 15 minutes = -80.25
    assert obs[0]["lon"] == pytest.approx(-80.25, abs=0.01)


def test_parse_hdob_pressure():
    result = parse_hdob_message(SAMPLE_HDOB)
    obs = result["observations"]

    # Static pressure: 7023 * 0.1 = 702.3 mb
    assert obs[0]["static_pressure_mb"] == pytest.approx(702.3, abs=0.1)
    # Extrapolated SLP: 0150 => 1000 + 15.0 = 1015.0
    assert obs[0]["extrapolated_slp_mb"] == pytest.approx(1015.0, abs=0.1)


def test_parse_hdob_wind():
    result = parse_hdob_message(SAMPLE_HDOB)
    obs = result["observations"]

    assert obs[0]["fl_wind_dir_deg"] == 270.0
    assert obs[0]["fl_wind_speed_kt"] == 65.0
    assert obs[0]["sfmr_sfc_wind_kt"] == 55.0
    assert obs[0]["sfmr_peak_sfc_wind_kt"] == 62.0


def test_parse_hdob_missing_values():
    result = parse_hdob_message(SAMPLE_HDOB)
    obs = result["observations"]

    # Third observation has /// for static pressure and other fields
    assert obs[2]["static_pressure_mb"] is None
    assert obs[2]["extrapolated_slp_mb"] is None
    assert obs[2]["dewpoint_c"] is None
    assert obs[2]["sfmr_sfc_wind_kt"] is None


def test_parse_hdob_temp():
    result = parse_hdob_message(SAMPLE_HDOB)
    obs = result["observations"]

    # +213 * 0.1 = 21.3 C
    assert obs[0]["temp_c"] == pytest.approx(21.3, abs=0.1)
    # +180 * 0.1 = 18.0 C
    assert obs[0]["dewpoint_c"] == pytest.approx(18.0, abs=0.1)


# ---------------------------------------------------------------------------
# VDM parser
# ---------------------------------------------------------------------------

SAMPLE_VDM = """URNT12 KNHC 071800
REPNT2
VORTEX DATA MESSAGE  AL142024

A. 071800 UTC
B. 2606N 08015W
C. 700 MB / 3050 M  GP
D. 950 MB
E. 270/12 KT
H. 120 KT
J. 135 KT
L. 110 KT
N. 130 KT
S. CLOSED WALL / 12 NM
$$
"""


def test_parse_vdm_message():
    result = parse_vdm_message(SAMPLE_VDM)

    assert result["storm_id"] == "AL142024"
    assert result["fix_time_utc"] == "071800"
    assert result["center_lat"] == pytest.approx(26.1, abs=0.01)
    assert result["center_lon"] == pytest.approx(-80.25, abs=0.01)
    assert result["min_slp_mb"] == 950
    assert result["max_sfmr_inbound_kt"] == 120
    assert result["max_fl_wind_inbound_kt"] == 135
    assert result["max_sfmr_outbound_kt"] == 110
    assert result["max_fl_wind_outbound_kt"] == 130


def test_parse_vdm_eye():
    result = parse_vdm_message(SAMPLE_VDM)
    assert result["eye_diameter_nm"] == 12
    assert "CLOSED WALL" in result["eye_character"]


def test_parse_vdm_flight_level():
    result = parse_vdm_message(SAMPLE_VDM)
    assert result["fl_pressure_mb"] == 700
    assert result["fl_height"] == 3050


# ---------------------------------------------------------------------------
# ATCF f-deck parser
# ---------------------------------------------------------------------------

SAMPLE_FDECK_LINE = "AL, 14, 2024100712,   , AIRC,   ,  281N,  0801W,  120,  950,"


def test_parse_atcf_fix_record():
    record = parse_atcf_fix_record(SAMPLE_FDECK_LINE)
    assert record is not None
    assert record["basin"] == "AL"
    assert record["cyclone_num"] == 14
    assert record["datetime"] == "2024100712"
    assert record["lat"] == pytest.approx(28.1, abs=0.1)
    assert record["lon"] == pytest.approx(-80.1, abs=0.1)
    assert record["max_wind_kt"] == 120
    assert record["min_pressure_mb"] == 950


def test_parse_atcf_fix_record_empty():
    assert parse_atcf_fix_record("") is None
    assert parse_atcf_fix_record("   ") is None


def test_parse_atcf_fix_record_short():
    assert parse_atcf_fix_record("AL, 14, 2024") is None


# ---------------------------------------------------------------------------
# ATCF lat/lon parser
# ---------------------------------------------------------------------------


def test_parse_atcf_latlon_basic():
    lat, lon = parse_atcf_latlon("281N", "0940W")
    assert lat == pytest.approx(28.1)
    assert lon == pytest.approx(-94.0)


def test_parse_atcf_latlon_southern():
    lat, lon = parse_atcf_latlon("125S", "1700E")
    assert lat == pytest.approx(-12.5)
    assert lon == pytest.approx(170.0)


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------


def test_format_tabular_data():
    data = [
        {"name": "Milton", "wind": 150},
        {"name": "Helene", "wind": 120},
    ]
    columns = [("name", "Name"), ("wind", "Wind (kt)")]
    result = format_tabular_data(data, columns, title="Test")

    assert "## Test" in result
    assert "| Name | Wind (kt) |" in result
    assert "| Milton | 150 |" in result
    assert "2 records returned" in result


def test_format_tabular_data_empty():
    result = format_tabular_data([], [("a", "A")], title="Empty")
    assert "0 records returned" in result
