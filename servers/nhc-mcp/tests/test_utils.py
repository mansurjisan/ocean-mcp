"""Unit tests for NHC MCP parsers, formatters, and utility functions."""

import pytest

from nhc_mcp.models import classify_wind_speed
from nhc_mcp.utils import (
    _positive_int_or_none,
    build_arcgis_query_url,
    build_track_geojson,
    format_tabular_data,
    get_arcgis_layer_id,
    handle_nhc_error,
    parse_atcf_bdeck,
    parse_atcf_latlon,
    parse_hurdat2,
    parse_hurdat2_latlon,
    parse_storm_id,
)


# ---------------------------------------------------------------------------
# ATCF coordinate parsing
# ---------------------------------------------------------------------------


class TestParseAtcfLatlon:
    def test_north_west(self):
        lat, lon = parse_atcf_latlon("281N", "0940W")
        assert lat == pytest.approx(28.1)
        assert lon == pytest.approx(-94.0)

    def test_south_east(self):
        lat, lon = parse_atcf_latlon("125S", "1700E")
        assert lat == pytest.approx(-12.5)
        assert lon == pytest.approx(170.0)

    def test_north_east(self):
        lat, lon = parse_atcf_latlon("350N", "0100E")
        assert lat == pytest.approx(35.0)
        assert lon == pytest.approx(10.0)

    def test_zero_lat(self):
        lat, lon = parse_atcf_latlon("000N", "0900W")
        assert lat == pytest.approx(0.0)
        assert lon == pytest.approx(-90.0)

    def test_whitespace_handling(self):
        lat, lon = parse_atcf_latlon("  281N  ", "  0940W  ")
        assert lat == pytest.approx(28.1)
        assert lon == pytest.approx(-94.0)


# ---------------------------------------------------------------------------
# HURDAT2 coordinate parsing (decimal degrees)
# ---------------------------------------------------------------------------


class TestParseHurdat2Latlon:
    def test_north_west(self):
        lat, lon = parse_hurdat2_latlon("23.8N", "75.7W")
        assert lat == pytest.approx(23.8)
        assert lon == pytest.approx(-75.7)

    def test_south_east(self):
        lat, lon = parse_hurdat2_latlon("12.5S", "170.0E")
        assert lat == pytest.approx(-12.5)
        assert lon == pytest.approx(170.0)

    def test_integer_degrees(self):
        lat, lon = parse_hurdat2_latlon("30.0N", "90.0W")
        assert lat == pytest.approx(30.0)
        assert lon == pytest.approx(-90.0)

    def test_whitespace(self):
        lat, lon = parse_hurdat2_latlon("  23.8N  ", "  75.7W  ")
        assert lat == pytest.approx(23.8)
        assert lon == pytest.approx(-75.7)


# ---------------------------------------------------------------------------
# Storm ID parsing
# ---------------------------------------------------------------------------


class TestParseStormId:
    def test_katrina(self):
        basin, number, year = parse_storm_id("AL092005")
        assert basin == "al"
        assert number == 9
        assert year == 2005

    def test_lowercase(self):
        basin, number, year = parse_storm_id("al092005")
        assert basin == "al"
        assert number == 9

    def test_east_pacific(self):
        basin, number, year = parse_storm_id("EP042023")
        assert basin == "ep"
        assert number == 4
        assert year == 2023

    def test_central_pacific(self):
        basin, number, year = parse_storm_id("CP012024")
        assert basin == "cp"
        assert number == 1
        assert year == 2024

    def test_invalid_basin(self):
        with pytest.raises(ValueError, match="Invalid storm ID"):
            parse_storm_id("XX012024")

    def test_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid storm ID"):
            parse_storm_id("KATRINA")

    def test_whitespace(self):
        basin, number, year = parse_storm_id("  AL092005  ")
        assert basin == "al"


# ---------------------------------------------------------------------------
# ArcGIS layer ID lookup
# ---------------------------------------------------------------------------


class TestGetArcgisLayerId:
    def test_at1_forecast_points(self):
        assert get_arcgis_layer_id("AT1", "forecast_points") == 6

    def test_at1_watch_warning(self):
        assert get_arcgis_layer_id("AT1", "watch_warning") == 9

    def test_at2_forecast_points(self):
        assert get_arcgis_layer_id("AT2", "forecast_points") == 32

    def test_at2_watch_warning(self):
        assert get_arcgis_layer_id("AT2", "watch_warning") == 35

    def test_ep1_forecast_points(self):
        assert get_arcgis_layer_id("EP1", "forecast_points") == 136

    def test_ep1_past_track(self):
        assert get_arcgis_layer_id("EP1", "past_track") == 142

    def test_cp1_forecast_points(self):
        assert get_arcgis_layer_id("CP1", "forecast_points") == 266

    def test_lowercase_input(self):
        assert get_arcgis_layer_id("at1", "forecast_points") == 6

    def test_invalid_bin(self):
        with pytest.raises(ValueError, match="Unknown bin_number"):
            get_arcgis_layer_id("ZZ9", "forecast_points")

    def test_invalid_layer_type(self):
        with pytest.raises(ValueError, match="Unknown layer_type"):
            get_arcgis_layer_id("AT1", "invalid_type")

    def test_at3_forecast_track(self):
        assert get_arcgis_layer_id("AT3", "forecast_track") == 59

    def test_at5_forecast_cone(self):
        assert get_arcgis_layer_id("AT5", "forecast_cone") == 112


# ---------------------------------------------------------------------------
# ArcGIS query URL builder
# ---------------------------------------------------------------------------


class TestBuildArcgisQueryUrl:
    def test_default_where(self):
        url = build_arcgis_query_url(6)
        assert "/6/query" in url
        assert "where=1%3D1" in url or "where=1=1" in url
        assert "f=json" in url

    def test_custom_where(self):
        url = build_arcgis_query_url(32, where="stormname='KATRINA'")
        assert "/32/query" in url
        assert "stormname" in url


# ---------------------------------------------------------------------------
# HURDAT2 parser
# ---------------------------------------------------------------------------

SAMPLE_HURDAT2 = """AL092005,            KATRINA,     34,
20050823, 1800,  , TD, 23.8N,  75.7W,  30, 1008,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
20050824, 0000,  , TD, 24.2N,  76.3W,  30, 1007,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
20050824, 0600,  , TD, 24.6N,  77.0W,  30, 1007,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
20050824, 1200,  , TS, 25.1N,  77.9W,  35, 1006,   50,    0,    0,   40,    0,    0,    0,    0,    0,    0,    0,    0,
20050824, 1800, L, TS, 25.8N,  78.9W,  40, 1003,   50,   30,    0,   40,    0,    0,    0,    0,    0,    0,    0,    0,
20050825, 0000,  , TS, 26.0N,  79.5W,  45, 1000,   60,   40,    0,   40,    0,    0,    0,    0,    0,    0,    0,    0,
20050825, 0600,  , TS, 26.1N,  80.6W,  50,  997,   60,   50,   25,   40,   20,    0,    0,    0,    0,    0,    0,    0,
20050825, 1200,  , TS, 26.1N,  81.7W,  55,  994,   80,   60,   30,   40,   30,   20,    0,    0,    0,    0,    0,    0,
20050825, 1800,  , HU, 26.0N,  82.8W,  70,  983,   80,   60,   30,   60,   30,   20,    0,   20,    0,    0,    0,    0,
20050826, 0000,  , HU, 25.9N,  83.9W,  80,  979,   90,   60,   40,   60,   40,   20,   15,   20,    0,    0,    0,    0,
20050826, 0600,  , HU, 25.5N,  84.9W,  90,  968,  105,   60,   40,   90,   45,   25,   15,   30,   15,    0,    0,    0,
20050826, 1200,  , HU, 25.3N,  85.6W, 100,  959,  105,   75,   50,   90,   50,   30,   25,   30,   20,   15,    0,    0,
20050826, 1800,  , HU, 25.2N,  86.2W, 100,  950,  120,   75,   50,   90,   50,   30,   25,   30,   20,   15,   15,   15,
20050827, 0000,  , HU, 25.1N,  86.7W, 100,  942,  120,   75,   50,  100,   60,   30,   25,   40,   25,   15,   15,   15,
20050827, 0600,  , HU, 25.1N,  87.2W, 105,  948,  120,   75,   60,  100,   60,   40,   30,   40,   25,   15,   15,   15,
20050827, 1200,  , HU, 25.3N,  87.8W, 125,  941,  120,   80,   60,  100,   60,   45,   35,   40,   25,   20,   15,   15,
20050827, 1800,  , HU, 25.6N,  88.5W, 145,  927,  120,  100,   60,  100,   60,   50,   40,   40,   30,   20,   15,   15,
20050828, 0000,  , HU, 25.9N,  88.6W, 150,  909,  120,  100,   70,  100,   60,   50,   40,   45,   30,   25,   15,   15,
20050828, 0600,  , HU, 26.3N,  88.6W, 145,  905,  120,  100,   70,  100,   60,   50,   45,   45,   30,   25,   15,   15,
20050828, 1200,  , HU, 27.0N,  89.0W, 150,  902,  120,  100,   80,  100,   60,   50,   50,   45,   35,   30,   20,   20,
20050828, 1800,  , HU, 27.8N,  89.2W, 140,  905,  150,  100,   75,  100,   75,   50,   45,   50,   35,   30,   20,   20,
20050829, 0000,  , HU, 28.8N,  89.3W, 125,  913,  150,  120,   75,  100,   90,   50,   45,   50,   40,   30,   25,   25,
20050829, 0600,  , HU, 29.7N,  89.4W, 110,  923,  150,  120,   75,  100,   90,   60,   45,   50,   40,   30,   25,   25,
20050829, 1100, L, HU, 30.4N,  89.5W, 110,  920,  150,  120,   75,  100,   90,   60,   50,   50,   40,   30,   25,   25,
20050829, 1200,  , HU, 30.6N,  89.6W, 105,  928,  150,  120,   75,  100,   90,   60,   50,   50,   40,   30,   25,   25,
20050829, 1800,  , HU, 31.4N,  89.5W,  75,  948,  150,  120,   50,   75,   90,   60,   25,   25,   40,   30,    0,    0,
20050830, 0000,  , TS, 32.7N,  89.3W,  55,  961,  150,  120,    0,   75,   50,   30,    0,    0,   30,    0,    0,    0,
20050830, 0600,  , TS, 34.1N,  89.1W,  40,  978,  125,  100,    0,   75,   25,    0,    0,    0,    0,    0,    0,    0,
20050830, 1200,  , TD, 35.3N,  88.4W,  30,  985,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
20050830, 1800,  , EX, 36.4N,  87.0W,  30,  990,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
20050831, 0000,  , EX, 37.5N,  85.0W,  30,  994,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
20050831, 0600,  , EX, 38.5N,  83.5W,  25,  996,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
20050831, 1200,  , EX, 39.5N,  83.0W,  25,  997,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
20050831, 1800,  , EX, 40.0N,  83.0W,  20, 1002,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
AL102005,                IDA,      5,
20050918, 1200,  , TD, 18.8N,  44.6W,  25, 1007,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
20050919, 0000,  , TD, 19.8N,  46.1W,  25, 1006,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
20050919, 1200,  , TD, 21.5N,  48.0W,  25, 1007,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
20050920, 0000,  , TD, 23.5N,  49.0W,  25, 1007,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
20050920, 1200,  , LO, 25.5N,  50.1W,  20, 1008,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,    0,
"""


class TestParseHurdat2:
    def test_parses_two_storms(self):
        storms = parse_hurdat2(SAMPLE_HURDAT2)
        assert len(storms) == 2

    def test_katrina_id(self):
        storms = parse_hurdat2(SAMPLE_HURDAT2)
        assert storms[0]["id"] == "AL092005"

    def test_katrina_name(self):
        storms = parse_hurdat2(SAMPLE_HURDAT2)
        assert storms[0]["name"] == "KATRINA"

    def test_katrina_track_count(self):
        storms = parse_hurdat2(SAMPLE_HURDAT2)
        assert storms[0]["num_entries"] == 34
        assert len(storms[0]["track"]) == 34

    def test_katrina_first_point(self):
        storms = parse_hurdat2(SAMPLE_HURDAT2)
        pt = storms[0]["track"][0]
        assert pt["date"] == "20050823"
        assert pt["time"] == "1800"
        assert pt["status"] == "TD"
        assert pt["lat"] == pytest.approx(23.8)
        assert pt["lon"] == pytest.approx(-75.7)
        assert pt["max_wind"] == 30
        assert pt["min_pressure"] == 1008

    def test_katrina_peak_wind(self):
        storms = parse_hurdat2(SAMPLE_HURDAT2)
        winds = [
            pt["max_wind"] for pt in storms[0]["track"] if pt["max_wind"] is not None
        ]
        assert max(winds) == 150  # Category 5

    def test_ida_id(self):
        storms = parse_hurdat2(SAMPLE_HURDAT2)
        assert storms[1]["id"] == "AL102005"
        assert storms[1]["name"] == "IDA"
        assert len(storms[1]["track"]) == 5


# ---------------------------------------------------------------------------
# ATCF B-deck parser
# ---------------------------------------------------------------------------

SAMPLE_BDECK = """AL, 09, 2005082318,   , BEST,   0, 238N,  757W,  30, 1008, TD,   0,    ,    0,    0,    0,    0,
AL, 09, 2005082400,   , BEST,   0, 242N,  763W,  30, 1007, TD,   0,    ,    0,    0,    0,    0,
AL, 09, 2005082406,   , BEST,   0, 246N,  770W,  30, 1007, TD,   0,    ,    0,    0,    0,    0,
AL, 09, 2005082412,   , BEST,   0, 251N,  779W,  35, 1006, TS,  34, NEQ,   50,    0,    0,   40,
AL, 09, 2005082418, L , BEST,   0, 258N,  789W,  40, 1003, TS,  34, NEQ,   50,   30,    0,   40,
AL, 09, 2005082500,   , BEST,   0, 260N,  795W,  45, 1000, TS,  34, NEQ,   60,   40,    0,   40,
AL, 09, 2005082812,   , BEST,   0, 270N,  890W, 150,  902, HU,  34, NEQ,  120,  100,   80,  100,
AL, 09, 2005082812,   , BEST,  12, 280N,  890W, 140,  905, HU,  34, NEQ,  120,  100,   80,  100,
"""


class TestParseAtcfBdeck:
    def test_parses_tau_zero_only(self):
        points = parse_atcf_bdeck(SAMPLE_BDECK)
        # 7 tau=0 entries, 1 tau=12 skipped
        assert len(points) == 7

    def test_first_point(self):
        points = parse_atcf_bdeck(SAMPLE_BDECK)
        pt = points[0]
        assert pt["basin"] == "AL"
        assert pt["cyclone_num"] == 9
        assert pt["lat"] == pytest.approx(23.8)
        assert pt["lon"] == pytest.approx(-75.7)
        assert pt["max_wind"] == 30
        assert pt["min_pressure"] == 1008
        assert pt["status"] == "TD"

    def test_peak_point(self):
        points = parse_atcf_bdeck(SAMPLE_BDECK)
        peak = points[-1]
        assert peak["max_wind"] == 150
        assert peak["lat"] == pytest.approx(27.0)

    def test_datetime_format(self):
        points = parse_atcf_bdeck(SAMPLE_BDECK)
        assert "2005-08-23 18:00 UTC" == points[0]["datetime"]


# ---------------------------------------------------------------------------
# Saffir-Simpson classification
# ---------------------------------------------------------------------------


class TestClassifyWindSpeed:
    def test_category_5(self):
        assert classify_wind_speed(150) == "Category 5"

    def test_category_4(self):
        assert classify_wind_speed(130) == "Category 4"

    def test_category_3(self):
        assert classify_wind_speed(100) == "Category 3"

    def test_category_2(self):
        assert classify_wind_speed(90) == "Category 2"

    def test_category_1(self):
        assert classify_wind_speed(65) == "Category 1"

    def test_tropical_storm(self):
        assert classify_wind_speed(50) == "Tropical Storm"

    def test_tropical_depression(self):
        assert classify_wind_speed(30) == "Tropical Depression"

    def test_boundary_cat5(self):
        assert classify_wind_speed(137) == "Category 5"

    def test_boundary_cat1(self):
        assert classify_wind_speed(64) == "Category 1"

    def test_zero_wind(self):
        assert classify_wind_speed(0) == "Tropical Depression"


# ---------------------------------------------------------------------------
# Tabular data formatter
# ---------------------------------------------------------------------------


class TestFormatTabularData:
    def test_basic_table(self):
        data = [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]
        columns = [("a", "Col A"), ("b", "Col B")]
        result = format_tabular_data(data, columns, title="Test")
        assert "## Test" in result
        assert "| Col A | Col B |" in result
        assert "| 1 | x |" in result
        assert "2 records returned" in result

    def test_with_metadata(self):
        data = [{"x": 1}]
        columns = [("x", "X")]
        result = format_tabular_data(data, columns, metadata_lines=["Info: test"])
        assert "**Info: test**" in result

    def test_empty_data(self):
        result = format_tabular_data([], [("a", "A")], title="Empty")
        assert "0 records returned" in result

    def test_custom_source(self):
        result = format_tabular_data([{"a": 1}], [("a", "A")], source="HURDAT2")
        assert "HURDAT2" in result


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------


class TestHandleNhcError:
    def test_value_error(self):
        result = handle_nhc_error(ValueError("bad input"), "parsing")
        assert "bad input" in result
        assert "parsing" in result

    def test_generic_error(self):
        result = handle_nhc_error(RuntimeError("oops"))
        assert "RuntimeError" in result
        assert "oops" in result

    def test_timeout_error(self):
        import httpx

        result = handle_nhc_error(httpx.ReadTimeout("timeout"))
        assert "timed out" in result

    def test_http_404(self):
        import httpx

        response = httpx.Response(404, request=httpx.Request("GET", "http://test"))
        err = httpx.HTTPStatusError(
            "not found", request=response.request, response=response
        )
        result = handle_nhc_error(err, "test operation")
        assert "404" in result
        assert "nhc_get_active_storms" in result


# ---------------------------------------------------------------------------
# Missing-value sentinels (wind/pressure)  -- regression
# ---------------------------------------------------------------------------

# Real HURDAT2 uses -99 for missing max wind (~57 records in the 1851-2024
# file) and -999 for missing pressure; ATCF b-deck uses 0. The parser
# previously only filtered -999 (HURDAT2) / empty (b-deck), so -99 and 0
# leaked into output and into classify_wind_speed (which mapped -99 to
# "Tropical Depression").

SENTINEL_HURDAT2 = """AL011900,            UNNAMED,      3,
19000901, 0000,  , HU, 28.0N,  94.8W,  80,  973,    0,    0,    0,    0,
19000901, 0600,  , HU, 28.0N,  95.4W, -99, -999,    0,    0,    0,    0,
19000901, 1200,  , TD, 28.1N,  96.5W,  30, -999,    0,    0,    0,    0,
"""

SENTINEL_BDECK = """AL, 01, 2005082318,   , BEST,   0, 238N,  757W,  30, 1008, TD,   0,
AL, 01, 2005082400,   , BEST,   0, 242N,  763W,   0,    0, DB,   0,
"""


class TestPositiveIntOrNone:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("80", 80),
            (" 902 ", 902),
            ("-99", None),  # HURDAT2 missing max wind
            ("-999", None),  # HURDAT2 missing pressure
            ("0", None),  # ATCF b-deck missing
            ("", None),
            ("   ", None),
            ("abc", None),
            ("-1", None),
        ],
    )
    def test_values(self, raw, expected):
        assert _positive_int_or_none(raw) == expected


class TestHurdat2MissingSentinels:
    def test_minus99_wind_becomes_none(self):
        """-99 max wind -> None (was leaking as -99)."""
        storm = parse_hurdat2(SENTINEL_HURDAT2)[0]
        bad = storm["track"][1]  # the -99 / -999 record
        assert bad["max_wind"] is None
        assert bad["min_pressure"] is None

    def test_minus999_pressure_becomes_none(self):
        storm = parse_hurdat2(SENTINEL_HURDAT2)[0]
        assert storm["track"][2]["min_pressure"] is None
        assert storm["track"][2]["max_wind"] == 30  # valid value kept

    def test_valid_values_unaffected(self):
        storm = parse_hurdat2(SENTINEL_HURDAT2)[0]
        good = storm["track"][0]
        assert good["max_wind"] == 80
        assert good["min_pressure"] == 973

    def test_missing_wind_not_classified_as_td(self):
        """The visible bug: classify_wind_speed(-99) returned 'Tropical
        Depression'. With None, callers (history.py) emit '' instead."""
        storm = parse_hurdat2(SENTINEL_HURDAT2)[0]
        assert storm["track"][1]["max_wind"] is None
        # Sanity: the old leaked value would have misclassified.
        assert classify_wind_speed(-99) == "Tropical Depression"


class TestBdeckMissingSentinels:
    def test_zero_wind_and_pressure_become_none(self):
        points = parse_atcf_bdeck(SENTINEL_BDECK)
        assert points[1]["max_wind"] is None
        assert points[1]["min_pressure"] is None

    def test_valid_bdeck_values_kept(self):
        points = parse_atcf_bdeck(SENTINEL_BDECK)
        assert points[0]["max_wind"] == 30
        assert points[0]["min_pressure"] == 1008


class TestBuildTrackGeojson:
    """Tests for the GeoJSON track builder."""

    POINTS = [
        {"lat": 25.0, "lon": -80.0, "max_wind": 90, "status": "HU"},
        {"lat": 26.5, "lon": -82.0, "max_wind": 110, "status": "HU"},
        {"lat": 28.0, "lon": -84.0, "max_wind": 80, "status": "HU"},
    ]

    def test_feature_collection_structure(self):
        gj = build_track_geojson(self.POINTS)
        assert gj["type"] == "FeatureCollection"
        kinds = [f["geometry"]["type"] for f in gj["features"]]
        assert kinds[0] == "LineString"  # track line first
        assert kinds.count("Point") == 3

    def test_coordinates_are_lon_lat_order(self):
        """GeoJSON is [longitude, latitude] (RFC 7946), not [lat, lon]."""
        gj = build_track_geojson(self.POINTS)
        line = gj["features"][0]
        assert line["geometry"]["coordinates"][0] == [-80.0, 25.0]
        assert line["geometry"]["coordinates"][-1] == [-84.0, 28.0]
        first_point = gj["features"][1]
        assert first_point["geometry"]["coordinates"] == [-80.0, 25.0]

    def test_line_and_point_properties(self):
        gj = build_track_geojson(
            self.POINTS,
            line_properties={"storm_id": "AL992026", "track_type": "best_track"},
            point_property_keys=["max_wind", "status"],
        )
        assert gj["features"][0]["properties"]["storm_id"] == "AL992026"
        pt_props = gj["features"][1]["properties"]
        assert pt_props == {"max_wind": 90, "status": "HU"}
        # lon/lat live in geometry, never duplicated into properties
        assert "lat" not in pt_props and "lon" not in pt_props

    def test_skips_invalid_coords_and_no_line_under_two_points(self):
        gj = build_track_geojson(
            [{"lat": None, "lon": -80.0}, {"lat": 25.0, "lon": -80.0}]
        )
        kinds = [f["geometry"]["type"] for f in gj["features"]]
        assert "LineString" not in kinds  # only 1 valid point, need >= 2
        assert kinds.count("Point") == 1
