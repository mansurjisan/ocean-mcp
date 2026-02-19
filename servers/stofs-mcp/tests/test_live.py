"""Live integration tests for STOFS MCP — requires internet access.

Run with: uv run pytest tests/test_live.py -v -s
"""

import pytest

from stofs_mcp.client import STOFSClient
from stofs_mcp.utils import parse_station_netcdf, resolve_latest_cycle, cleanup_temp_file


@pytest.fixture
async def client():
    c = STOFSClient()
    yield c
    await c.close()


@pytest.mark.asyncio
async def test_check_latest_2d_cycle_exists(client):
    """Verify that at least one recent STOFS-2D-Global cycle exists on S3."""
    result = await resolve_latest_cycle(client, "2d_global", num_days=3)
    assert result is not None, (
        "No STOFS-2D-Global cycle found in the last 3 days. "
        "S3 bucket may be unavailable or there's a network issue."
    )
    date_str, cycle_str = result
    assert len(date_str) == 8  # YYYYMMDD
    assert cycle_str in ("00", "06", "12", "18")
    print(f"\nLatest 2D cycle: {date_str} {cycle_str}z")


@pytest.mark.asyncio
async def test_download_and_parse_station_file(client):
    """Download a STOFS-2D station file and verify NetCDF dimensions."""
    cycle = await resolve_latest_cycle(client, "2d_global", num_days=3)
    assert cycle is not None, "No cycle available to test"

    date_str, hour_str = cycle
    url = client.build_station_url("2d_global", date_str, hour_str, "cwl")

    tmp_path = None
    try:
        tmp_path = await client.download_netcdf(url)
        assert tmp_path.exists()
        assert tmp_path.stat().st_size > 100_000  # At least 100 KB

        meta = parse_station_netcdf(tmp_path)
        print(f"\nStations: {meta['n_stations']}, Time steps: {meta['n_times']}")

        assert meta["n_stations"] > 100, "Expected 100+ stations in STOFS-2D"
        assert meta["n_times"] > 100, "Expected 100+ time steps"
        assert len(meta["lats"]) > 0
        assert len(meta["lons"]) > 0
    finally:
        cleanup_temp_file(tmp_path)


@pytest.mark.asyncio
async def test_extract_single_station(client):
    """Download STOFS-2D file and extract The Battery (8518750) time series."""
    cycle = await resolve_latest_cycle(client, "2d_global", num_days=3)
    assert cycle is not None

    date_str, hour_str = cycle
    url = client.build_station_url("2d_global", date_str, hour_str, "cwl")

    tmp_path = None
    try:
        tmp_path = await client.download_netcdf(url)
        data = parse_station_netcdf(tmp_path, "8518750")

        print(f"\nThe Battery: {len(data['times'])} time steps")
        print(f"First: {data['times'][0] if data['times'] else 'N/A'}")
        print(f"Last:  {data['times'][-1] if data['times'] else 'N/A'}")

        assert len(data["times"]) > 0, "Expected non-empty time series for The Battery"
        assert len(data["values"]) == len(data["times"])
        assert data["lat"] is not None
        assert data["lon"] is not None
        # The Battery should be near 40.7N, 74.0W
        assert 39.0 < data["lat"] < 42.0
        assert -76.0 < data["lon"] < -72.0
    finally:
        cleanup_temp_file(tmp_path)


@pytest.mark.asyncio
async def test_coops_observation_fetch(client):
    """Fetch 24 hours of CO-OPS water level data for The Battery."""
    from datetime import datetime, timedelta, timezone

    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=24)

    begin_str = start.strftime("%Y%m%d %H:%M")
    end_str = end.strftime("%Y%m%d %H:%M")

    data = await client.fetch_coops_observations("8518750", begin_str, end_str, datum="MSL")

    assert "data" in data, "Expected 'data' key in CO-OPS response"
    records = data["data"]
    assert len(records) > 0, "Expected at least some observations"

    # Check structure
    sample = records[0]
    assert "t" in sample, "Expected 't' (time) field"
    assert "v" in sample, "Expected 'v' (value) field"
    print(f"\nCO-OPS observations: {len(records)} records")
    print(f"Sample: {sample}")


@pytest.mark.asyncio
async def test_opendap_endpoint_reachable(client):
    """Check that the NOMADS OPeNDAP endpoint is reachable for the latest cycle."""
    from stofs_mcp.utils import get_opendap_region

    cycle = await resolve_latest_cycle(client, "2d_global", num_days=3)
    if cycle is None:
        pytest.skip("No STOFS cycle found")

    date_str, hour_str = cycle
    # The Battery, NY → conus.east region
    region = get_opendap_region(40.7, -74.0)
    url = client.build_opendap_url("2d_global", date_str, hour_str, region)
    available = await client.check_opendap_available(url)

    if not available:
        pytest.skip("NOMADS OPeNDAP not reachable (may be temporarily down or outside 2-day window)")

    print(f"\nOPeNDAP reachable: {url}")


@pytest.mark.asyncio
async def test_opendap_point_extraction(client):
    """Extract a single point from STOFS via OPeNDAP at The Battery, NY."""
    from stofs_mcp.utils import extract_point_from_opendap, get_opendap_region

    cycle = await resolve_latest_cycle(client, "2d_global", num_days=3)
    if cycle is None:
        pytest.skip("No STOFS cycle found")

    date_str, hour_str = cycle
    # The Battery, NY — conus.east region
    region = get_opendap_region(40.7, -74.0)
    url = client.build_opendap_url("2d_global", date_str, hour_str, region)
    available = await client.check_opendap_available(url)
    if not available:
        pytest.skip("NOMADS OPeNDAP not reachable")

    data = extract_point_from_opendap(url, 40.7, -74.0)

    print(f"\nVariable: {data['variable']}")
    print(f"Grid point: ({data['actual_lat']}, {data['actual_lon']})")
    print(f"Resolution: {data['grid_resolution_deg']}°")
    print(f"Time steps: {data['n_times']}")
    if data["times"]:
        print(f"First: {data['times'][0]}, Last: {data['times'][-1]}")

    assert data["n_times"] > 0, "Expected at least some data points"
    assert len(data["values"]) == len(data["times"])
    # Grid point should be near the requested location
    assert abs(data["actual_lat"] - 40.7) < 0.5
    assert abs(data["actual_lon"] - (-74.0)) < 0.5


@pytest.mark.asyncio
async def test_3d_atlantic_station_file(client):
    """Download STOFS-3D-Atlantic station file and verify structure."""
    cycle = await resolve_latest_cycle(client, "3d_atlantic", num_days=3)

    if cycle is None:
        pytest.skip("No STOFS-3D-Atlantic cycle found in last 3 days — possibly not yet published")

    date_str, hour_str = cycle
    url = client.build_station_url("3d_atlantic", date_str, hour_str, "cwl")

    tmp_path = None
    try:
        tmp_path = await client.download_netcdf(url)
        assert tmp_path.exists()

        meta = parse_station_netcdf(tmp_path)
        print(f"\n3D Atlantic stations: {meta['n_stations']}, Time steps: {meta['n_times']}")

        # 3D has fewer stations (~108) but should still be substantial
        assert meta["n_stations"] > 50
        assert meta["n_times"] > 50
    finally:
        cleanup_temp_file(tmp_path)
