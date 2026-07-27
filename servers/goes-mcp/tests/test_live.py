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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_full_disk_default_resolution_download(client: GOESClient) -> None:
    """FD's default resolution (1808x1808) must actually exist on STAR CDN.

    Before the per-coverage fix, every tool defaulted to CONUS's
    '1250x750', which 404s for FD — this pins the replacement default.
    """
    url = client.build_latest_url(
        satellite="goes-19",
        coverage="FD",
        product="GEOCOLOR",
        resolution="1808x1808",
    )
    assert url.endswith("/FD/GEOCOLOR/1808x1808.jpg")

    img_bytes = await client.get_image(url)

    assert len(img_bytes) > 1000
    assert img_bytes[:2] == b"\xff\xd8", "Not a valid JPEG"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_sector_default_resolution_download(client: GOESClient) -> None:
    """SECTOR's default resolution (1200x1200) must actually exist on STAR CDN.

    Before the fix, goes_get_sector_image also defaulted to CONUS's
    '1250x750', which 404s for every regional sector.
    """
    url = client.build_sector_url(
        satellite="goes-19",
        sector="se",
        product="GEOCOLOR",
        resolution="1200x1200",
    )
    assert url.endswith("/SECTOR/se/GEOCOLOR/1200x1200.jpg")

    img_bytes = await client.get_image(url)

    assert len(img_bytes) > 1000
    assert img_bytes[:2] == b"\xff\xd8", "Not a valid JPEG"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_timestamp_chain_slider_to_image(client: GOESClient) -> None:
    """goes_get_available_times' raw output must chain into goes_get_image.

    Fetches a real 14-digit SLIDER timestamp and feeds it straight into
    build_timestamped_url (unconverted) — this is exactly what the
    goes_get_image docstring promises the model it can do.
    """
    timestamps = await client.get_slider_times(
        satellite="goes-19", sector="CONUS", product="GEOCOLOR", limit=1
    )
    assert timestamps, "Expected at least one timestamp"
    slider_timestamp = timestamps[0]
    assert len(slider_timestamp) == 14

    url = client.build_timestamped_url(
        satellite="goes-19",
        coverage="CONUS",
        product="GEOCOLOR",
        timestamp=slider_timestamp,
        resolution="1250x750",
    )

    img_bytes = await client.get_image(url)

    assert len(img_bytes) > 1000
    assert img_bytes[:2] == b"\xff\xd8", "Not a valid JPEG"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_slider_times_lowercase_fd(client: GOESClient) -> None:
    """sector='fd' (lowercase) must resolve on SLIDER the same as 'FD'."""
    timestamps = await client.get_slider_times(
        satellite="goes-19", sector="fd", product="GEOCOLOR", limit=1
    )
    assert len(timestamps) == 1
    assert timestamps[0].isdigit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_slider_times_rejects_regional_sector(client: GOESClient) -> None:
    """A regional SECTOR/xx sub-sector should be rejected before hitting SLIDER.

    Verified live: SLIDER has no 'southeast' (or northeast/caribbean/
    tropical_atlantic/puerto_rico) path for goes-19 — only conus/full_disk.
    """
    from goes_mcp.client import GOESAPIError

    with pytest.raises(GOESAPIError, match="does not publish timestamps"):
        await client.get_slider_times(
            satellite="goes-19", sector="se", product="GEOCOLOR"
        )
