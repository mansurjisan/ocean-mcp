"""Unit tests for OFS MCP utils — no network required."""

from __future__ import annotations

import pytest

from ofs_mcp.client import OFSClient
from ofs_mcp.models import OFS_MODELS
from ofs_mcp.utils import (
    align_timeseries,
    compute_validation_stats,
    find_nearest_fvcom,
    find_nearest_roms,
    haversine,
)


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------

def test_haversine_known_distance():
    # NYC to LA: roughly 3940 km
    dist = haversine(40.7128, -74.0060, 34.0522, -118.2437)
    assert 3900 < dist < 3980


def test_haversine_zero():
    assert haversine(0.0, 0.0, 0.0, 0.0) == pytest.approx(0.0)


def test_haversine_short():
    # ~111 km per degree of latitude
    dist = haversine(0.0, 0.0, 1.0, 0.0)
    assert 110 < dist < 113


# ---------------------------------------------------------------------------
# Validation statistics
# ---------------------------------------------------------------------------

def test_validation_stats_perfect():
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    stats = compute_validation_stats(vals, vals)
    assert stats["bias"] == pytest.approx(0.0)
    assert stats["rmse"] == pytest.approx(0.0)
    assert stats["mae"] == pytest.approx(0.0)
    assert stats["peak_error"] == pytest.approx(0.0)
    assert stats["n"] == 5


def test_validation_stats_known_bias():
    forecast = [1.1, 2.1, 3.1]
    observed = [1.0, 2.0, 3.0]
    stats = compute_validation_stats(forecast, observed)
    assert stats["bias"] == pytest.approx(0.1, abs=1e-4)
    assert stats["rmse"] == pytest.approx(0.1, abs=1e-4)
    assert stats["mae"] == pytest.approx(0.1, abs=1e-4)
    assert stats["correlation"] == pytest.approx(1.0, abs=1e-6)


def test_validation_stats_empty():
    stats = compute_validation_stats([], [])
    assert stats["n"] == 0
    assert stats["bias"] is None


def test_validation_stats_mismatched_lengths():
    stats = compute_validation_stats([1.0, 2.0], [1.0])
    assert stats["n"] == 0


# ---------------------------------------------------------------------------
# Time series alignment
# ---------------------------------------------------------------------------

def test_align_timeseries_exact_match():
    t_f = ["2026-02-19 00:00", "2026-02-19 01:00", "2026-02-19 02:00"]
    v_f = [1.0, 2.0, 3.0]
    t_o = ["2026-02-19 00:00", "2026-02-19 01:00", "2026-02-19 02:00"]
    v_o = [1.1, 2.1, 3.1]

    common, af, ao = align_timeseries(t_f, v_f, t_o, v_o)
    assert len(common) == 3
    assert af == v_f
    assert ao == v_o


def test_align_timeseries_partial_overlap():
    t_f = ["2026-02-19 00:00", "2026-02-19 01:00", "2026-02-19 02:00"]
    v_f = [1.0, 2.0, 3.0]
    t_o = ["2026-02-19 01:00", "2026-02-19 02:00", "2026-02-19 03:00"]
    v_o = [2.1, 3.1, 4.1]

    common, af, ao = align_timeseries(t_f, v_f, t_o, v_o)
    assert len(common) == 2
    assert af == [2.0, 3.0]
    assert ao == [2.1, 3.1]


def test_align_timeseries_tolerance():
    # 5-minute offset, within default 10-minute tolerance
    t_f = ["2026-02-19 00:00"]
    v_f = [1.0]
    t_o = ["2026-02-19 00:05"]
    v_o = [1.1]

    common, af, ao = align_timeseries(t_f, v_f, t_o, v_o, tolerance_minutes=10)
    assert len(common) == 1


def test_align_timeseries_outside_tolerance():
    t_f = ["2026-02-19 00:00"]
    v_f = [1.0]
    t_o = ["2026-02-19 01:00"]
    v_o = [1.1]

    common, af, ao = align_timeseries(t_f, v_f, t_o, v_o, tolerance_minutes=10)
    assert len(common) == 0


# ---------------------------------------------------------------------------
# S3 URL construction
# ---------------------------------------------------------------------------

def test_s3_url_cbofs_forecast():
    client = OFSClient()
    url = client.build_s3_url("cbofs", "20260219", "06", "f", 1)
    assert "noaa-nos-ofs-pds" in url
    assert "cbofs/netcdf/2026/02/19" in url
    assert "cbofs.t06z.fields.f001.nc" in url


def test_s3_url_ngofs2_nowcast():
    client = OFSClient()
    url = client.build_s3_url("ngofs2", "20260219", "12", "n", 3)
    assert "ngofs2/netcdf/2026/02/19" in url
    assert "ngofs2.t12z.fields.n003.nc" in url


def test_s3_url_wcofs():
    client = OFSClient()
    url = client.build_s3_url("wcofs", "20260219", "03", "f", 48)
    assert "wcofs/netcdf/2026/02/19" in url
    assert "wcofs.t03z.fields.f048.nc" in url


# ---------------------------------------------------------------------------
# THREDDS URL construction
# ---------------------------------------------------------------------------

def test_thredds_url_cbofs():
    client = OFSClient()
    url = client.build_thredds_url("cbofs")
    assert "opendap.co-ops.nos.noaa.gov" in url
    assert "CBOFS" in url
    assert "CBOFS_BEST.nc" in url


def test_thredds_url_ngofs2():
    client = OFSClient()
    url = client.build_thredds_url("ngofs2")
    assert "NGOFS2" in url
    assert "NGOFS2_BEST.nc" in url


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------

def test_all_models_have_required_keys():
    required = ["name", "short_name", "grid_type", "domain", "cycles",
                "forecast_hours", "datum", "nc_vars", "thredds_id"]
    for model_id, info in OFS_MODELS.items():
        for key in required:
            assert key in info, f"Model '{model_id}' missing key '{key}'"


def test_model_nc_vars_have_time_and_water_level():
    for model_id, info in OFS_MODELS.items():
        nc_vars = info["nc_vars"]
        assert "time" in nc_vars, f"Model '{model_id}' missing nc_vars['time']"
        assert "water_level" in nc_vars, f"Model '{model_id}' missing nc_vars['water_level']"


def test_roms_models_have_lon_rho():
    for model_id, info in OFS_MODELS.items():
        if info["grid_type"] == "roms":
            assert info["nc_vars"]["lon"] in ["lon_rho", "lon"], \
                f"ROMS model '{model_id}' should have lon_rho coordinate"


def test_fvcom_models_have_lon():
    for model_id, info in OFS_MODELS.items():
        if info["grid_type"] == "fvcom":
            assert info["nc_vars"]["lon"] == "lon", \
                f"FVCOM model '{model_id}' should have lon coordinate"


# ---------------------------------------------------------------------------
# Find nearest point (offline — using simple synthetic grids)
# ---------------------------------------------------------------------------

def test_find_nearest_fvcom_known_point():
    import numpy as np
    lats = np.array([38.0, 38.5, 39.0, 39.5])
    lons = np.array([-76.0, -76.5, -77.0, -77.5])

    result = find_nearest_fvcom(38.49, -76.48, lats, lons, max_distance_km=50.0)
    assert result is not None
    idx, dist = result
    assert idx == 1  # Nearest to (38.5, -76.5)
    assert dist < 5.0


def test_find_nearest_fvcom_out_of_range():
    import numpy as np
    lats = np.array([38.0])
    lons = np.array([-76.0])

    result = find_nearest_fvcom(60.0, -76.0, lats, lons, max_distance_km=50.0)
    assert result is None


def test_find_nearest_roms_known_point():
    import numpy as np
    # Simple 3x3 rho grid
    lats = np.array([[38.0, 38.0, 38.0],
                      [38.5, 38.5, 38.5],
                      [39.0, 39.0, 39.0]])
    lons = np.array([[-77.0, -76.5, -76.0],
                      [-77.0, -76.5, -76.0],
                      [-77.0, -76.5, -76.0]])

    result = find_nearest_roms(38.49, -76.49, lats, lons, max_distance_km=50.0)
    assert result is not None
    i, j, dist = result
    assert (i, j) == (1, 1)  # Middle cell nearest to (38.5, -76.5)
    assert dist < 5.0


def test_find_nearest_roms_out_of_range():
    import numpy as np
    lats = np.array([[38.0]])
    lons = np.array([[-76.0]])

    result = find_nearest_roms(50.0, -76.0, lats, lons, max_distance_km=50.0)
    assert result is None


# ---------------------------------------------------------------------------
# Domain coverage
# ---------------------------------------------------------------------------

def test_chesapeake_bay_in_cbofs_domain():
    domain = OFS_MODELS["cbofs"]["domain"]
    lat, lon = 38.98, -76.48  # Chesapeake Bay
    assert domain["lat_min"] <= lat <= domain["lat_max"]
    assert domain["lon_min"] <= lon <= domain["lon_max"]


def test_san_francisco_in_sfbofs_domain():
    domain = OFS_MODELS["sfbofs"]["domain"]
    lat, lon = 37.77, -122.42  # San Francisco
    assert domain["lat_min"] <= lat <= domain["lat_max"]
    assert domain["lon_min"] <= lon <= domain["lon_max"]


def test_alaska_in_ciofs_domain():
    domain = OFS_MODELS["ciofs"]["domain"]
    lat, lon = 60.5, -150.8  # Kenai area
    assert domain["lat_min"] <= lat <= domain["lat_max"]
    assert domain["lon_min"] <= lon <= domain["lon_max"]
