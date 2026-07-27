"""Unit tests for recon_mcp.utils parsers — no network access needed."""

import json

import pytest

from recon_mcp.utils import (
    _parse_atcf_fix_latlon,
    _parse_hdob_latlon,
    _parse_vdm_latlon,
    format_json_response,
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


def test_parse_hdob_latlon_rejects_wrong_length():
    # Wrong-length values (column-shifted or malformed input) must return None
    # rather than silently producing bogus coordinates.
    assert _parse_hdob_latlon("12345N", is_lat=True) is None  # 5 digits in lat slot
    assert _parse_hdob_latlon("260N", is_lat=True) is None  # 3 digits in lat slot
    assert _parse_hdob_latlon("0801W", is_lat=False) is None  # 4 digits in lon slot
    assert _parse_hdob_latlon("099999W", is_lat=False) is None  # 6 digits in lon slot
    # Minutes >= 60 are invalid.
    assert _parse_hdob_latlon("2660N", is_lat=True) is None
    # Non-digit body must be rejected.
    assert _parse_hdob_latlon("AB12N", is_lat=True) is None
    # Valid inputs still parse.
    assert _parse_hdob_latlon("2606N", is_lat=True) == pytest.approx(26.1, abs=0.01)
    assert _parse_hdob_latlon("08015W", is_lat=False) == pytest.approx(-80.25, abs=0.01)


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


def test_parse_vdm_latlon_rejects_wrong_length():
    # Same silent-corruption class as HDOB: a wrong-column or garbled VDM
    # B-field value must return None, not a bogus storm-center fix.
    assert _parse_vdm_latlon("12345N", is_lat=True) is None  # 5 digits in lat
    assert _parse_vdm_latlon("260N", is_lat=True) is None  # 3 digits in lat
    assert _parse_vdm_latlon("0801W", is_lat=False) is None  # 4 digits in lon
    assert _parse_vdm_latlon("099999W", is_lat=False) is None  # 6 digits in lon
    # Minutes >= 60 are invalid.
    assert _parse_vdm_latlon("2660N", is_lat=True) is None
    # Non-digit body must be rejected.
    assert _parse_vdm_latlon("AB12N", is_lat=True) is None
    assert _parse_vdm_latlon("", is_lat=True) is None
    # Valid DDMM / DDDMM inputs still parse (matches the docstring examples).
    assert _parse_vdm_latlon("2606N", is_lat=True) == pytest.approx(26.1, abs=0.01)
    assert _parse_vdm_latlon("08015W", is_lat=False) == pytest.approx(-80.25, abs=0.01)


# ---------------------------------------------------------------------------
# ATCF f-deck parser
# ---------------------------------------------------------------------------

# Real f-deck: lat is 4-digit, lon 5-digit, both hundredths of a degree.
SAMPLE_FDECK_LINE = "AL, 14, 2024100712,   , AIRC,   ,  2810N,  08010W,  120,  950,"


def test_parse_atcf_fix_record():
    record = parse_atcf_fix_record(SAMPLE_FDECK_LINE)
    assert record is not None
    assert record["basin"] == "AL"
    assert record["cyclone_num"] == 14
    assert record["datetime"] == "2024100712"
    # Hundredths, not tenths: 2810N → 28.10, 08010W → -80.10.
    assert record["lat"] == pytest.approx(28.10, abs=0.001)
    assert record["lon"] == pytest.approx(-80.10, abs=0.001)
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


# The two tests above also guard against a regression: parse_atcf_latlon is
# TENTHS-of-a-degree and is shared by the b-deck best-track parser. The f-deck
# fix parser must NOT reuse it (f-deck is hundredths) — see below.


def test_parse_atcf_fix_latlon_hundredths():
    # F-deck is hundredths of a degree, 4-digit lat / 5-digit lon.
    assert _parse_atcf_fix_latlon("2557N", is_lat=True) == pytest.approx(25.57)
    assert _parse_atcf_fix_latlon("08015W", is_lat=False) == pytest.approx(-80.15)
    assert _parse_atcf_fix_latlon("1250S", is_lat=True) == pytest.approx(-12.50)
    assert _parse_atcf_fix_latlon("17000E", is_lat=False) == pytest.approx(170.0)


def test_parse_atcf_fix_latlon_rejects_wrong_format():
    # Tenths-format (b-deck) values fed to the f-deck parser are wrong-length
    # and must return None instead of a silently 10x-wrong coordinate.
    assert _parse_atcf_fix_latlon("281N", is_lat=True) is None  # 3-digit (tenths)
    assert _parse_atcf_fix_latlon("0940W", is_lat=False) is None  # 4-digit (tenths)
    # Other off-spec / wrong-column inputs.
    assert _parse_atcf_fix_latlon("12345N", is_lat=True) is None  # 5 digits in lat
    assert _parse_atcf_fix_latlon("099999W", is_lat=False) is None  # 6 in lon
    assert _parse_atcf_fix_latlon("9500N", is_lat=True) is None  # > 90.00 deg
    assert _parse_atcf_fix_latlon("18500W", is_lat=False) is None  # > 180.00 deg
    assert _parse_atcf_fix_latlon("202308061200", is_lat=False) is None  # datetime
    assert _parse_atcf_fix_latlon("AB12N", is_lat=True) is None  # non-digit body
    assert _parse_atcf_fix_latlon("2557X", is_lat=True) is None  # bad hemisphere
    assert _parse_atcf_fix_latlon("", is_lat=True) is None


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


def test_format_tabular_data_under_cap_not_truncated():
    """When data fits under max_rows, no truncation footer is added."""
    data = [{"name": f"Storm{i}"} for i in range(5)]
    result = format_tabular_data(data, [("name", "Name")], max_rows=10)
    assert "5 records returned" in result
    assert "truncated" not in result.lower()


def test_format_tabular_data_max_rows_keeps_head_by_default():
    """keep='head' (the default) keeps the first max_rows rows."""
    data = [{"name": f"Storm{i}"} for i in range(10)]
    result = format_tabular_data(data, [("name", "Name")], max_rows=3)
    assert "Storm0" in result
    assert "Storm1" in result
    assert "Storm2" in result
    assert "Storm9" not in result
    assert "Showing the first 3 of 10 records" in result
    assert "(truncated)" in result


def test_format_tabular_data_max_rows_keeps_tail_when_requested():
    """keep='tail' keeps the most recent (last) max_rows rows."""
    data = [{"name": f"Storm{i}"} for i in range(10)]
    result = format_tabular_data(data, [("name", "Name")], max_rows=3, keep="tail")
    assert "Storm7" in result
    assert "Storm8" in result
    assert "Storm9" in result
    assert "Storm0" not in result
    assert "Showing the most recent 3 of 10 records" in result


# ---------------------------------------------------------------------------
# format_json_response — truncation envelope
# ---------------------------------------------------------------------------


def test_format_json_response_list_not_truncated():
    """A list under max_records carries truncated=False and matching counts."""
    data = [{"i": i} for i in range(3)]
    result = json.loads(format_json_response(data, max_records=10))

    assert result["truncated"] is False
    assert result["record_count"] == 3
    assert result["total_count"] == 3
    assert "hint" not in result
    assert len(result["data"]) == 3
    assert "retrieved_at" in result


def test_format_json_response_list_truncated_head():
    """keep='head' (default) keeps the first max_records records and hints."""
    data = [{"i": i} for i in range(10)]
    result = json.loads(format_json_response(data, max_records=3))

    assert result["truncated"] is True
    assert result["record_count"] == 3
    assert result["total_count"] == 10
    assert [d["i"] for d in result["data"]] == [0, 1, 2]
    assert "hint" in result
    assert "first" in result["hint"].lower()


def test_format_json_response_list_truncated_tail():
    """keep='tail' keeps the most recent (last) max_records records."""
    data = [{"i": i} for i in range(10)]
    result = json.loads(format_json_response(data, max_records=3, keep="tail"))

    assert result["truncated"] is True
    assert result["record_count"] == 3
    assert result["total_count"] == 10
    assert [d["i"] for d in result["data"]] == [7, 8, 9]
    assert "most recent" in result["hint"].lower()


def test_format_json_response_dict_passthrough():
    """Dict payloads are merged in as-is (no list-shaped truncation applied)."""
    payload = {"storm": "Milton", "missions": [1, 2, 3]}
    result = json.loads(format_json_response(payload, context="test context"))

    assert result["storm"] == "Milton"
    assert result["missions"] == [1, 2, 3]
    assert result["context"] == "test context"
    assert "retrieved_at" in result


def test_format_json_response_context_included():
    result = json.loads(format_json_response([], context="some context"))
    assert result["context"] == "some context"
