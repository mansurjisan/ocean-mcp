"""Live integration tests against real GOES APIs."""

import pytest

from goes_mcp.client import GOESClient


@pytest.fixture
async def client():
    """Create a GOESClient and close it after the test."""
    c = GOESClient()
    yield c
    await c.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_slider_timestamps(client: GOESClient) -> None:
    """Fetch real SLIDER timestamps for GOES-19 CONUS GeoColor."""
    timestamps = await client.get_slider_times(
        satellite="goes-19",
        sector="CONUS",
        product="GEOCOLOR",
        limit=5,
    )

    assert len(timestamps) > 0, "Expected at least one timestamp"
    assert len(timestamps) <= 5
    # Each timestamp should be 14 digits (YYYYMMDDHHmmss)
    for ts in timestamps:
        assert len(ts) == 14, f"Expected 14-digit timestamp, got {ts}"
        assert ts.isdigit(), f"Timestamp should be all digits: {ts}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_download_thumbnail(client: GOESClient) -> None:
    """Download a real thumbnail from STAR CDN."""
    url = client.build_latest_url(
        satellite="goes-19",
        coverage="CONUS",
        product="GEOCOLOR",
        resolution="thumbnail",
    )

    img_bytes = await client.get_image(url)

    # Should be a valid JPEG (starts with FF D8)
    assert len(img_bytes) > 1000, f"Thumbnail too small: {len(img_bytes)} bytes"
    assert img_bytes[:2] == b"\xff\xd8", "Not a valid JPEG (missing SOI marker)"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_full_disk_thumbnail(client: GOESClient) -> None:
    """Download a Full Disk thumbnail from STAR CDN."""
    url = client.build_latest_url(
        satellite="goes-19",
        coverage="FD",
        product="GEOCOLOR",
        resolution="thumbnail",
    )

    img_bytes = await client.get_image(url)

    assert len(img_bytes) > 1000, f"Thumbnail too small: {len(img_bytes)} bytes"
    assert img_bytes[:2] == b"\xff\xd8", "Not a valid JPEG"
