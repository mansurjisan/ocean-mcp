"""Unit tests for SFMR utilities — no network access needed."""

from datetime import datetime, timezone

import numpy as np
import pytest

from recon_mcp.models import AIRCRAFT_CODES
from recon_mcp.utils import (
    cleanup_temp_file,
    compute_radial_wind_profile,
    haversine,
    interpolate_track_position,
    parse_atcf_best_track,
)


# ---------------------------------------------------------------------------
# Haversine
# ---------------------------------------------------------------------------


def test_haversine_equator_one_degree():
    """One degree of longitude at the equator ≈ 111 km."""
    dist = haversine(0.0, 0.0, 0.0, 1.0)
    assert abs(dist - 111.19) < 1.0


def test_haversine_same_point():
    dist = haversine(26.0, -80.0, 26.0, -80.0)
    assert dist == pytest.approx(0.0, abs=1e-6)


def test_haversine_known_distance():
    """New York to London ≈ 5570 km."""
    dist = haversine(40.7128, -74.0060, 51.5074, -0.1278)
    assert abs(dist - 5570) < 20


def test_haversine_vectorized():
    """Vectorized computation with numpy arrays."""
    lats = np.array([0.0, 0.0, 0.0])
    lons = np.array([1.0, 2.0, 3.0])
    dists = haversine(0.0, 0.0, lats, lons)
    assert len(dists) == 3
    assert dists[0] == pytest.approx(111.19, abs=1.0)
    assert dists[1] == pytest.approx(222.39, abs=1.0)
    assert dists[2] == pytest.approx(333.58, abs=2.0)


# ---------------------------------------------------------------------------
# ATCF best track parser
# ---------------------------------------------------------------------------

SAMPLE_BDECK = """AL, 09, 2022092600,   , BEST,   0,  197N,  0835W,  40,  998, TS,   0,    ,    0,    0,    0,    0,
AL, 09, 2022092606,   , BEST,   0,  199N,  0841W,  45,  996, TS,   0,    ,    0,    0,    0,    0,
AL, 09, 2022092612,   , BEST,   0,  201N,  0848W,  55,  990, TS,   0,    ,    0,    0,    0,    0,
AL, 09, 2022092618,   , BEST,   0,  205N,  0855W,  65,  982, HU,   0,    ,    0,    0,    0,    0,
AL, 09, 2022092700,   , BEST,   0,  213N,  0862W,  85,  965, HU,   0,    ,    0,    0,    0,    0,
"""


def test_parse_atcf_best_track_basic():
    track = parse_atcf_best_track(SAMPLE_BDECK)
    assert len(track) == 5
    assert track[0]["lat"] == pytest.approx(19.7, abs=0.1)
    assert track[0]["lon"] == pytest.approx(-83.5, abs=0.1)
    assert track[0]["max_wind_kt"] == 40
    assert track[0]["min_slp_mb"] == 998


def test_parse_atcf_best_track_sorted():
    track = parse_atcf_best_track(SAMPLE_BDECK)
    for i in range(len(track) - 1):
        assert track[i]["datetime"] <= track[i + 1]["datetime"]


def test_parse_atcf_best_track_datetime():
    track = parse_atcf_best_track(SAMPLE_BDECK)
    assert track[0]["datetime"] == datetime(2022, 9, 26, 0, tzinfo=timezone.utc)
    assert track[1]["datetime"] == datetime(2022, 9, 26, 6, tzinfo=timezone.utc)


def test_parse_atcf_best_track_empty():
    assert parse_atcf_best_track("") == []
    assert parse_atcf_best_track("   \n  \n") == []


# ---------------------------------------------------------------------------
# Interpolate track position
# ---------------------------------------------------------------------------


def test_interpolate_track_midpoint():
    """Interpolating at the midpoint between two track entries."""
    track = parse_atcf_best_track(SAMPLE_BDECK)
    # Midpoint between 00Z and 06Z on Sep 26
    mid_time = datetime(2022, 9, 26, 3, tzinfo=timezone.utc)
    pos = interpolate_track_position(track, mid_time)
    assert pos is not None
    lat, lon = pos
    # Should be approximately midway between 19.7/-83.5 and 19.9/-84.1
    assert lat == pytest.approx(19.8, abs=0.15)
    assert lon == pytest.approx(-83.8, abs=0.5)


def test_interpolate_track_at_exact_point():
    """Interpolating at an exact track point."""
    track = parse_atcf_best_track(SAMPLE_BDECK)
    pos = interpolate_track_position(track, track[0]["datetime"])
    assert pos is not None
    lat, lon = pos
    assert lat == pytest.approx(track[0]["lat"], abs=0.01)
    assert lon == pytest.approx(track[0]["lon"], abs=0.01)


def test_interpolate_track_before_start():
    """Before track start — clamps to first point."""
    track = parse_atcf_best_track(SAMPLE_BDECK)
    early = datetime(2022, 9, 25, 0, tzinfo=timezone.utc)
    pos = interpolate_track_position(track, early)
    assert pos is not None
    assert pos[0] == pytest.approx(track[0]["lat"])


def test_interpolate_track_after_end():
    """After track end — clamps to last point."""
    track = parse_atcf_best_track(SAMPLE_BDECK)
    late = datetime(2022, 10, 1, 0, tzinfo=timezone.utc)
    pos = interpolate_track_position(track, late)
    assert pos is not None
    assert pos[0] == pytest.approx(track[-1]["lat"])


def test_interpolate_track_empty():
    assert interpolate_track_position([], datetime(2022, 9, 26, 0, tzinfo=timezone.utc)) is None


# ---------------------------------------------------------------------------
# Compute radial wind profile
# ---------------------------------------------------------------------------


def test_compute_radial_wind_profile_synthetic():
    """Synthetic data: observations at known radii from a fixed center."""
    track = [
        {
            "datetime": datetime(2022, 9, 26, 0, tzinfo=timezone.utc),
            "lat": 20.0,
            "lon": -80.0,
            "max_wind_kt": 100,
            "min_slp_mb": 960,
        },
        {
            "datetime": datetime(2022, 9, 27, 0, tzinfo=timezone.utc),
            "lat": 20.0,
            "lon": -80.0,
            "max_wind_kt": 100,
            "min_slp_mb": 960,
        },
    ]

    # Create observations at ~0, ~50, ~100 km from center
    # At 20N, 1 degree lon ≈ 104.6 km
    n = 30
    lats = np.full(n, 20.0)
    lons = np.array([
        -80.0,      # ~0 km
        -80.0,
        -80.0,
        -80.0,
        -80.0,
        -80.0,
        -80.0,
        -80.0,
        -80.0,
        -80.0,
        -79.5,      # ~52 km
        -79.5,
        -79.5,
        -79.5,
        -79.5,
        -79.5,
        -79.5,
        -79.5,
        -79.5,
        -79.5,
        -79.0,      # ~104 km
        -79.0,
        -79.0,
        -79.0,
        -79.0,
        -79.0,
        -79.0,
        -79.0,
        -79.0,
        -79.0,
    ])
    # Winds: low at center, peak at ~50 km, drop at ~100 km
    sws = np.array([
        10.0, 12.0, 11.0, 13.0, 10.0, 11.0, 12.0, 10.0, 11.0, 10.0,
        50.0, 55.0, 52.0, 48.0, 53.0, 51.0, 54.0, 49.0, 50.0, 52.0,
        30.0, 28.0, 32.0, 29.0, 31.0, 30.0, 28.0, 33.0, 29.0, 31.0,
    ])
    srr = np.zeros(n)
    datetimes = [datetime(2022, 9, 26, 12, tzinfo=timezone.utc)] * n

    sfmr_data = {
        "datetime": datetimes,
        "lat": lats,
        "lon": lons,
        "sws": sws,
        "srr": srr,
        "n_obs": n,
    }

    profile = compute_radial_wind_profile(sfmr_data, track, bin_size_km=10.0)
    assert len(profile) > 0

    # Check that peak is in a mid-range bin (around 50 km)
    peak_bin = max(profile, key=lambda b: b["max_wind_ms"])
    assert 40 <= peak_bin["radius_min_km"] <= 60

    # First bin should have low winds
    first_bin = profile[0]
    assert first_bin["mean_wind_ms"] < 15


def test_compute_radial_wind_profile_empty():
    """No valid observations."""
    sfmr_data = {
        "datetime": [],
        "lat": np.array([]),
        "lon": np.array([]),
        "sws": np.array([]),
        "srr": np.array([]),
        "n_obs": 0,
    }
    track = [
        {
            "datetime": datetime(2022, 9, 26, 0, tzinfo=timezone.utc),
            "lat": 20.0,
            "lon": -80.0,
            "max_wind_kt": 100,
            "min_slp_mb": 960,
        },
    ]
    profile = compute_radial_wind_profile(sfmr_data, track)
    assert profile == []


# ---------------------------------------------------------------------------
# Aircraft code decode
# ---------------------------------------------------------------------------


def test_aircraft_codes():
    assert "U" in AIRCRAFT_CODES
    assert "H" in AIRCRAFT_CODES
    assert "I" in AIRCRAFT_CODES
    assert "N" in AIRCRAFT_CODES
    assert "USAF" in AIRCRAFT_CODES["U"]
    assert "P-3" in AIRCRAFT_CODES["H"]


def test_decode_sfmr_filename():
    from recon_mcp.tools.sfmr import _decode_sfmr_filename

    info = _decode_sfmr_filename("AFRC_SFMR20220926H1.nc")
    assert info["date"] == "20220926"
    assert info["aircraft_code"] == "H"
    assert info["aircraft"] == "NOAA N42RF (P-3)"
    assert info["mission_seq"] == "1"


def test_decode_sfmr_filename_usaf():
    from recon_mcp.tools.sfmr import _decode_sfmr_filename

    info = _decode_sfmr_filename("AFRC_SFMR20200825U2.nc")
    assert info["date"] == "20200825"
    assert info["aircraft_code"] == "U"
    assert info["aircraft"] == "USAF WC-130J"
    assert info["mission_seq"] == "2"


def test_decode_sfmr_filename_unknown():
    from recon_mcp.tools.sfmr import _decode_sfmr_filename

    info = _decode_sfmr_filename("somefile.nc")
    assert info["date"] is None
    assert info["aircraft_code"] is None


# ---------------------------------------------------------------------------
# Cleanup helper
# ---------------------------------------------------------------------------


def test_cleanup_temp_file_none():
    """Calling with None should not raise."""
    cleanup_temp_file(None)


def test_cleanup_temp_file_missing():
    """Calling with nonexistent path should not raise."""
    cleanup_temp_file("/tmp/nonexistent_sfmr_file_xyz123.nc")
