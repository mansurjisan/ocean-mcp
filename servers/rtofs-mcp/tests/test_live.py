"""Integration tests that hit the live HYCOM THREDDS server.

Run with: pytest tests/test_live.py -v
These are excluded from CI unit test runs.
"""

import math

import pytest

from rtofs_mcp.client import RTOFSClient


@pytest.fixture
async def client():
    """Create and clean up a live client."""
    c = RTOFSClient()
    yield c
    await c.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_ssh_point_query(client):
    """Fetch SSH at The Battery, NYC from HYCOM THREDDS."""
    rows = await client.fetch_point_csv(
        dataset_key="ssh",
        variable="surf_el",
        latitude=40.7,
        longitude=-74.0,
        time="present",
    )
    assert len(rows) >= 1, "Expected at least one SSH value"
    assert "surf_el" in rows[0]
    val = rows[0]["surf_el"]
    assert isinstance(val, float)
    assert not math.isnan(val), "SSH should not be NaN at The Battery"
    # SSH should be reasonable (between -5 and 5 meters)
    assert -5.0 < val < 5.0
    print(f"\nSSH at The Battery: {val:.4f} m")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_sst_surface_timeseries(client):
    """Fetch SST time series at The Battery, NYC."""
    rows = await client.fetch_point_csv(
        dataset_key="sst",
        variable="water_temp",
        latitude=40.7,
        longitude=-74.0,
        vert_coord=0.0,  # Surface
    )
    valid = [r for r in rows if not math.isnan(r.get("water_temp", float("nan")))]
    assert len(valid) >= 5, f"Expected >=5 valid SST rows, got {len(valid)}"
    print(f"\nSST time series: {len(valid)} points")
    print(f"  First: {valid[0]['time']} → {valid[0]['water_temp']:.2f} °C")
    print(f"  Last:  {valid[-1]['time']} → {valid[-1]['water_temp']:.2f} °C")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_temperature_profile(client):
    """Fetch temperature depth profile in the Gulf Stream."""
    rows = await client.fetch_point_csv(
        dataset_key="sst",
        variable="water_temp",
        latitude=35.0,
        longitude=-74.0,  # Gulf Stream area
        time="present",
    )
    valid = [r for r in rows if not math.isnan(r.get("water_temp", float("nan")))]
    assert len(valid) >= 3, "Expected at least 3 valid depth levels"
    print("\nTemperature profile (Gulf Stream, 35°N 74°W):")
    for r in valid[:10]:
        print(f"  {r.get('vertCoord', 0):.0f} m: {r['water_temp']:.2f} °C")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_dataset_availability(client):
    """Check that key datasets are available on HYCOM THREDDS."""
    for key in ["ssh", "sst", "sss", "currents"]:
        available = await client.check_dataset_available(key)
        print(f"\n  {key}: {'available' if available else 'unavailable'}")
        assert available, f"Dataset '{key}' should be available"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_salinity_point(client):
    """Fetch salinity at a mid-ocean point."""
    rows = await client.fetch_point_csv(
        dataset_key="sss",
        variable="salinity",
        latitude=30.0,
        longitude=-50.0,  # Mid-Atlantic
        time="present",
        vert_coord=0.0,
    )
    assert len(rows) >= 1
    val = rows[0]["salinity"]
    assert not math.isnan(val), "Salinity should not be NaN at mid-ocean"
    # Ocean salinity is typically 33-37 PSU
    assert 30.0 < val < 40.0, f"Salinity {val} PSU is outside expected range"
    print(f"\nSalinity at (30°N, 50°W): {val:.2f} PSU")
