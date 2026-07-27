"""Unit tests for goes-mcp tool functions with mocked HTTP responses."""

import json
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from goes_mcp.client import (
    GOESClient,
    GOESAPIError,
    RetryTransport,
    handle_goes_error,
)
from goes_mcp.models import SLIDER_BASE_URL, STAR_CDN_BASE
from tests.conftest import load_fixture, load_fixture_bytes


@pytest.fixture
def coops_client() -> GOESClient:
    """Create a bare GOESClient (backoff_factor=0 so retries replay instantly)."""
    return GOESClient(backoff_factor=0)


@pytest.fixture
def ctx(coops_client: GOESClient) -> MagicMock:
    """Create a mock Context wired to the GOESClient."""
    mock_ctx = MagicMock()
    mock_ctx.request_context.lifespan_context = {"goes_client": coops_client}
    return mock_ctx


@pytest.mark.asyncio
async def test_client_uses_retry_transport() -> None:
    """The shared httpx client is mounted on the RetryTransport."""
    c = GOESClient()
    client = await c._get_client()
    try:
        assert isinstance(client._transport, RetryTransport)
    finally:
        await c.close()


class TestHandleGoesError:
    """handle_goes_error gives typed, actionable messages (not a raw repr)."""

    def test_goes_api_error(self) -> None:
        assert handle_goes_error(GOESAPIError("no such product")) == (
            "GOES Error: no such product"
        )

    def test_http_status_error(self) -> None:
        req = httpx.Request("GET", "https://example.com/img.jpg")
        exc = httpx.HTTPStatusError(
            "boom", request=req, response=httpx.Response(404, request=req)
        )
        msg = handle_goes_error(exc)
        assert "HTTP 404" in msg
        assert "goes_get_available_times" in msg

    def test_timeout_error(self) -> None:
        msg = handle_goes_error(httpx.TimeoutException("slow"))
        assert "timed out" in msg.lower()
        assert "markdown" in msg

    def test_generic_error(self) -> None:
        msg = handle_goes_error(ValueError("weird"))
        assert "ValueError" in msg
        assert "weird" in msg


class TestGoesListProducts:
    """Tests for the goes_list_products tool."""

    @pytest.mark.asyncio
    async def test_list_products_markdown(self, ctx: MagicMock) -> None:
        """List products returns markdown with band and composite tables."""
        from goes_mcp.tools.products import goes_list_products

        result = await goes_list_products(ctx, response_format="markdown")

        assert "## ABI Bands" in result
        assert "## Composite Products" in result
        assert "GEOCOLOR" in result
        assert "GeoColor" in result
        assert "## GOES Satellites" in result
        assert "## Resolutions" in result

    @pytest.mark.asyncio
    async def test_list_products_json(self, ctx: MagicMock) -> None:
        """List products returns valid JSON with all sections."""
        from goes_mcp.tools.products import goes_list_products

        result = await goes_list_products(ctx, response_format="json")
        data = json.loads(result)

        assert "satellites" in data
        assert "bands" in data
        assert "composites" in data
        assert len(data["bands"]) == 16
        assert "GEOCOLOR" in data["composites"]

    @pytest.mark.asyncio
    async def test_list_products_contains_all_bands(self, ctx: MagicMock) -> None:
        """Markdown output should reference all 16 ABI bands."""
        from goes_mcp.tools.products import goes_list_products

        result = await goes_list_products(ctx, response_format="markdown")

        for i in range(1, 17):
            assert f"| {i:02d} |" in result, f"Band {i:02d} missing from output"


class TestGoesGetAvailableTimes:
    """Tests for the goes_get_available_times tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_available_times_markdown(self, ctx: MagicMock) -> None:
        """Fetch timestamps and verify markdown table output."""
        from goes_mcp.tools.products import goes_get_available_times

        fixture = load_fixture("slider_latest_times.json")
        respx.get(url__startswith=SLIDER_BASE_URL).mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await goes_get_available_times(
            ctx, satellite="goes-19", sector="CONUS", product="GEOCOLOR", limit=5
        )

        assert "Available Times" in result
        assert "GEOCOLOR" in result
        assert "2026-03-05" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_available_times_json(self, ctx: MagicMock) -> None:
        """Fetch timestamps and verify JSON output."""
        from goes_mcp.tools.products import goes_get_available_times

        fixture = load_fixture("slider_latest_times.json")
        respx.get(url__startswith=SLIDER_BASE_URL).mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await goes_get_available_times(
            ctx,
            satellite="goes-19",
            sector="CONUS",
            product="GEOCOLOR",
            limit=3,
            response_format="json",
        )
        data = json.loads(result)

        assert data["satellite"] == "goes-19"
        assert data["product"] == "GEOCOLOR"
        assert data["count"] == 3
        assert len(data["timestamps"]) == 3

    @respx.mock
    @pytest.mark.asyncio
    async def test_available_times_api_error(self, ctx: MagicMock) -> None:
        """API error should return user-friendly error message."""
        from goes_mcp.tools.products import goes_get_available_times

        respx.get(url__startswith=SLIDER_BASE_URL).mock(
            return_value=httpx.Response(500)
        )

        result = await goes_get_available_times(ctx)
        assert "Error" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_available_times_lowercase_fd_is_normalized(
        self, ctx: MagicMock
    ) -> None:
        """sector='fd' (lowercase) must resolve the same as 'FD'.

        Before the fix, only the exact-case 'FD' matched SLIDER_SECTORS;
        'fd' fell through to the literal string 'fd' as the SLIDER path
        segment and 404d.
        """
        from goes_mcp.tools.products import goes_get_available_times

        fixture = load_fixture("slider_latest_times.json")
        route = respx.get(url__regex=r".*/goes-19/full_disk/geocolor/.*").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await goes_get_available_times(
            ctx, satellite="goes-19", sector="fd", product="GEOCOLOR", limit=3
        )

        assert route.called
        assert "Error" not in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_available_times_rejects_unsupported_sector(
        self, ctx: MagicMock
    ) -> None:
        """A regional SECTOR/xx sub-sector should be rejected, not 404 on SLIDER.

        Verified live: SLIDER only publishes 'conus'/'full_disk' for
        goes-19/18 — 'se'/'ne'/'car'/'taw'/'pr' all 404 there.
        """
        from goes_mcp.tools.products import goes_get_available_times

        result = await goes_get_available_times(
            ctx, satellite="goes-19", sector="se", product="GEOCOLOR"
        )

        assert "Error" in result
        assert "se" in result
        assert "goes_get_sector_image" in result


class TestGoesGetLatestImage:
    """Tests for the goes_get_latest_image tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_latest_image_markdown(self, ctx: MagicMock) -> None:
        """Fetch latest image with markdown format returns URL and metadata."""
        from goes_mcp.tools.imagery import goes_get_latest_image

        result = await goes_get_latest_image(
            ctx,
            satellite="goes-19",
            coverage="CONUS",
            product="GEOCOLOR",
            resolution="1250x750",
            response_format="markdown",
        )

        assert "Latest GeoColor" in result
        assert "GOES-19" in result
        assert "cdn.star.nesdis.noaa.gov" in result
        assert "1250x750.jpg" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_latest_image_default_is_markdown(self, ctx: MagicMock) -> None:
        """Default response_format is now markdown (URL), not an embedded image."""
        from goes_mcp.tools.imagery import goes_get_latest_image

        result = await goes_get_latest_image(
            ctx, satellite="goes-19", coverage="CONUS", product="GEOCOLOR"
        )
        assert isinstance(result, str)
        assert "cdn.star.nesdis.noaa.gov" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_latest_image_fd_default_resolution(self, ctx: MagicMock) -> None:
        """FD with no resolution given should default to '1808x1808', not CONUS's 1250x750.

        Before the per-coverage fix every tool defaulted to '1250x750',
        which doesn't exist in FD's (square) ladder and 404s live.
        """
        from goes_mcp.tools.imagery import goes_get_latest_image

        result = await goes_get_latest_image(
            ctx,
            satellite="goes-19",
            coverage="FD",
            product="GEOCOLOR",
            response_format="json",
        )
        data = json.loads(result)

        assert data["resolution"] == "1808x1808"
        assert data["url"].endswith("1808x1808.jpg")

    @respx.mock
    @pytest.mark.asyncio
    async def test_latest_image_invalid_resolution_for_coverage(
        self, ctx: MagicMock
    ) -> None:
        """Requesting a CONUS-shaped resolution for FD should error with valid options."""
        from goes_mcp.tools.imagery import goes_get_latest_image

        result = await goes_get_latest_image(
            ctx,
            satellite="goes-19",
            coverage="FD",
            product="GEOCOLOR",
            resolution="1250x750",
            response_format="markdown",
        )

        assert "Error" in result
        assert "1808x1808" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_latest_image_json(self, ctx: MagicMock) -> None:
        """Fetch latest image with JSON format returns structured metadata."""
        from goes_mcp.tools.imagery import goes_get_latest_image

        result = await goes_get_latest_image(
            ctx,
            satellite="goes-19",
            coverage="CONUS",
            product="GEOCOLOR",
            response_format="json",
        )
        data = json.loads(result)

        assert data["satellite"] == "goes-19"
        assert data["coverage"] == "CONUS"
        assert data["product"] == "GEOCOLOR"
        assert "url" in data
        assert "GOES19" in data["url"]

    @respx.mock
    @pytest.mark.asyncio
    async def test_latest_image_returns_image(self, ctx: MagicMock) -> None:
        """Fetch latest image with response_format='image' returns an Image object."""
        from mcp.server.fastmcp.utilities.types import Image

        from goes_mcp.tools.imagery import goes_get_latest_image

        test_bytes = load_fixture_bytes("test_image.jpg")
        respx.get(url__startswith=STAR_CDN_BASE).mock(
            return_value=httpx.Response(
                200, content=test_bytes, headers={"content-type": "image/jpeg"}
            )
        )

        result = await goes_get_latest_image(
            ctx,
            satellite="goes-19",
            coverage="CONUS",
            product="GEOCOLOR",
            response_format="image",
        )

        assert isinstance(result, Image)

    @respx.mock
    @pytest.mark.asyncio
    async def test_latest_image_http_error(self, ctx: MagicMock) -> None:
        """HTTP error should return user-friendly error message."""
        from goes_mcp.tools.imagery import goes_get_latest_image

        respx.get(url__startswith=STAR_CDN_BASE).mock(return_value=httpx.Response(404))

        result = await goes_get_latest_image(ctx, response_format="image")
        assert isinstance(result, str)
        assert "Error" in result


class TestGoesGetImage:
    """Tests for the goes_get_image tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_image_markdown(self, ctx: MagicMock) -> None:
        """Fetch timestamped image with markdown format."""
        from goes_mcp.tools.imagery import goes_get_image

        result = await goes_get_image(
            ctx,
            timestamp="20260642031",
            satellite="goes-19",
            coverage="CONUS",
            product="GEOCOLOR",
            response_format="markdown",
        )

        assert "GEOCOLOR" in result
        assert "20260642031" in result
        assert "cdn.star.nesdis.noaa.gov" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_image_returns_image(self, ctx: MagicMock) -> None:
        """Fetch timestamped image with response_format='image' returns an Image object."""
        from mcp.server.fastmcp.utilities.types import Image

        from goes_mcp.tools.imagery import goes_get_image

        test_bytes = load_fixture_bytes("test_image.jpg")
        respx.get(url__startswith=STAR_CDN_BASE).mock(
            return_value=httpx.Response(
                200, content=test_bytes, headers={"content-type": "image/jpeg"}
            )
        )

        result = await goes_get_image(
            ctx, timestamp="20260642031", response_format="image"
        )

        assert isinstance(result, Image)

    @pytest.mark.asyncio
    async def test_get_image_invalid_timestamp(self, ctx: MagicMock) -> None:
        """Invalid timestamp format should return error."""
        from goes_mcp.tools.imagery import goes_get_image

        result = await goes_get_image(
            ctx, timestamp="2026-03-05", response_format="markdown"
        )
        assert "Error" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_image_accepts_14_digit_slider_timestamp(
        self, ctx: MagicMock
    ) -> None:
        """A raw goes_get_available_times timestamp (14-digit) should be accepted.

        goes_get_available_times returns YYYYMMDDHHmmss and its docstring
        tells the model to feed that straight into goes_get_image — this is
        the chain that was previously broken (goes_get_image hard-rejected
        anything but the 11-digit day-of-year format).
        """
        from goes_mcp.tools.imagery import goes_get_image

        result = await goes_get_image(
            ctx,
            timestamp="20260305202617",
            satellite="goes-19",
            coverage="CONUS",
            product="GEOCOLOR",
            response_format="markdown",
        )

        assert "Error" not in result
        # 2026-03-05 20:26:17 UTC is day-of-year 064 -> YYYYDDDHHmm = 20260642026
        assert "20260642026" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_image_fd_default_resolution(self, ctx: MagicMock) -> None:
        """FD timestamped image with no resolution should default to '1808x1808'."""
        from goes_mcp.tools.imagery import goes_get_image

        result = await goes_get_image(
            ctx,
            timestamp="20260642031",
            satellite="goes-19",
            coverage="FD",
            product="GEOCOLOR",
            response_format="json",
        )
        data = json.loads(result)

        assert data["resolution"] == "1808x1808"
        assert data["url"].endswith("1808x1808.jpg")


class TestGoesGetSectorImage:
    """Tests for the goes_get_sector_image tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_sector_image_markdown(self, ctx: MagicMock) -> None:
        """Fetch sector image with markdown format."""
        from goes_mcp.tools.imagery import goes_get_sector_image

        result = await goes_get_sector_image(
            ctx,
            sector="se",
            satellite="goes-19",
            product="GEOCOLOR",
            response_format="markdown",
        )

        assert "Southeast" in result
        assert "SECTOR/se" in result
        assert "cdn.star.nesdis.noaa.gov" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_sector_image_default_resolution(self, ctx: MagicMock) -> None:
        """Sector image with no resolution should default to '1200x1200'.

        Before the fix, every tool defaulted to CONUS's '1250x750', which
        doesn't exist in SECTOR's (square) ladder and 404s live.
        """
        from goes_mcp.tools.imagery import goes_get_sector_image

        result = await goes_get_sector_image(
            ctx, sector="se", satellite="goes-19", response_format="json"
        )
        data = json.loads(result)

        assert data["resolution"] == "1200x1200"
        assert data["url"].endswith("1200x1200.jpg")

    @respx.mock
    @pytest.mark.asyncio
    async def test_sector_image_json(self, ctx: MagicMock) -> None:
        """Fetch sector image with JSON format returns structured data."""
        from goes_mcp.tools.imagery import goes_get_sector_image

        result = await goes_get_sector_image(ctx, sector="car", response_format="json")
        data = json.loads(result)

        assert data["sector"] == "car"
        assert data["sector_name"] == "Caribbean"
        assert "url" in data

    @respx.mock
    @pytest.mark.asyncio
    async def test_sector_image_returns_image(self, ctx: MagicMock) -> None:
        """Fetch sector image with response_format='image' returns an Image object."""
        from mcp.server.fastmcp.utilities.types import Image

        from goes_mcp.tools.imagery import goes_get_sector_image

        test_bytes = load_fixture_bytes("test_image.jpg")
        respx.get(url__startswith=STAR_CDN_BASE).mock(
            return_value=httpx.Response(
                200, content=test_bytes, headers={"content-type": "image/jpeg"}
            )
        )

        result = await goes_get_sector_image(ctx, sector="ne", response_format="image")
        assert isinstance(result, Image)

    @pytest.mark.asyncio
    async def test_sector_image_invalid_sector(self, ctx: MagicMock) -> None:
        """Invalid sector code should return error."""
        from goes_mcp.tools.imagery import goes_get_sector_image

        result = await goes_get_sector_image(
            ctx, sector="midwest", response_format="markdown"
        )
        assert "Error" in result


class TestGoesGetCurrentView:
    """Tests for the goes_get_current_view tool."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_current_view_markdown(self, ctx: MagicMock) -> None:
        """Current view returns markdown summary table."""
        from goes_mcp.tools.imagery import goes_get_current_view

        fixture = load_fixture("slider_latest_times.json")
        respx.get(url__startswith=SLIDER_BASE_URL).mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await goes_get_current_view(ctx, satellite="goes-19")

        assert "Current GOES Imagery" in result
        assert "GOES-19" in result
        assert "CONUS" in result
        assert "Available Coverages" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_current_view_json(self, ctx: MagicMock) -> None:
        """Current view returns valid JSON with availability data."""
        from goes_mcp.tools.imagery import goes_get_current_view

        fixture = load_fixture("slider_latest_times.json")
        respx.get(url__startswith=SLIDER_BASE_URL).mock(
            return_value=httpx.Response(200, json=fixture)
        )

        result = await goes_get_current_view(
            ctx, satellite="goes-19", response_format="json"
        )
        data = json.loads(result)

        assert data["satellite"] == "goes-19"
        assert "availability" in data
        assert len(data["availability"]) > 0


class TestClientURLBuilding:
    """Tests for GOESClient URL building methods."""

    def test_build_latest_url(self) -> None:
        """Build correct latest image URL."""
        client = GOESClient()
        url = client.build_latest_url("goes-19", "CONUS", "GEOCOLOR", "1250x750")
        assert url == f"{STAR_CDN_BASE}/GOES19/ABI/CONUS/GEOCOLOR/1250x750.jpg"

    def test_build_sector_url(self) -> None:
        """Build correct sector image URL."""
        client = GOESClient()
        url = client.build_sector_url("goes-19", "se", "GEOCOLOR", "thumbnail")
        assert url == f"{STAR_CDN_BASE}/GOES19/ABI/SECTOR/se/GEOCOLOR/thumbnail.jpg"

    def test_build_timestamped_url(self) -> None:
        """Build correct timestamped image URL."""
        client = GOESClient()
        url = client.build_timestamped_url(
            "goes-19", "CONUS", "GEOCOLOR", "20260642031", "1250x750"
        )
        expected = f"{STAR_CDN_BASE}/GOES19/ABI/CONUS/GEOCOLOR/20260642031_GOES19-ABI-CONUS-GEOCOLOR-1250x750.jpg"
        assert url == expected

    def test_build_timestamped_url_invalid_timestamp(self) -> None:
        """Invalid timestamp format should raise ValueError."""
        client = GOESClient()
        with pytest.raises(ValueError, match="Invalid timestamp"):
            client.build_timestamped_url(
                "goes-19", "CONUS", "GEOCOLOR", "bad", "1250x750"
            )

    def test_build_latest_url_full_disk(self) -> None:
        """Build correct Full Disk URL."""
        client = GOESClient()
        url = client.build_latest_url("goes-18", "FD", "13", "latest")
        assert url == f"{STAR_CDN_BASE}/GOES18/ABI/FD/13/latest.jpg"

    def test_build_latest_url_fd_default_resolution_shape(self) -> None:
        """FD's default resolution ('1808x1808') builds a URL that isn't CONUS-shaped."""
        client = GOESClient()
        url = client.build_latest_url("goes-19", "FD", "GEOCOLOR", "1808x1808")
        assert url == f"{STAR_CDN_BASE}/GOES19/ABI/FD/GEOCOLOR/1808x1808.jpg"

    def test_build_sector_url_default_resolution_shape(self) -> None:
        """SECTOR's default resolution ('1200x1200') builds a URL that isn't CONUS-shaped."""
        client = GOESClient()
        url = client.build_sector_url("goes-19", "se", "GEOCOLOR", "1200x1200")
        assert url == f"{STAR_CDN_BASE}/GOES19/ABI/SECTOR/se/GEOCOLOR/1200x1200.jpg"

    def test_build_latest_url_rejects_conus_resolution_for_fd(self) -> None:
        """A CONUS-shaped resolution must be rejected for FD coverage.

        Before per-coverage validation, every tool defaulted to CONUS's
        '1250x750' regardless of coverage, so FD requests always 404d live.
        """
        client = GOESClient()
        with pytest.raises(ValueError, match="Unknown resolution '1250x750' for FD"):
            client.build_latest_url("goes-19", "FD", "GEOCOLOR", "1250x750")

    def test_build_sector_url_rejects_conus_resolution(self) -> None:
        """A CONUS-shaped resolution must be rejected for SECTOR coverage."""
        client = GOESClient()
        with pytest.raises(
            ValueError, match="Unknown resolution '1250x750' for SECTOR"
        ):
            client.build_sector_url("goes-19", "se", "GEOCOLOR", "1250x750")

    def test_build_timestamped_url_accepts_14_digit_slider_timestamp(self) -> None:
        """A 14-digit SLIDER timestamp (YYYYMMDDHHmmss) should convert to STAR CDN's format."""
        client = GOESClient()
        url = client.build_timestamped_url(
            "goes-19", "CONUS", "GEOCOLOR", "20260305202617", "1250x750"
        )
        # 2026-03-05 20:26:17 UTC -> day-of-year 064 -> YYYYDDDHHmm = 20260642026
        expected = (
            f"{STAR_CDN_BASE}/GOES19/ABI/CONUS/GEOCOLOR/"
            "20260642026_GOES19-ABI-CONUS-GEOCOLOR-1250x750.jpg"
        )
        assert url == expected

    def test_build_timestamped_url_fd_latest_uses_fd_largest_size(self) -> None:
        """FD + resolution='latest' should embed FD's largest size (10848x10848), not CONUS's 5000x3000."""
        client = GOESClient()
        url = client.build_timestamped_url(
            "goes-19", "FD", "GEOCOLOR", "20260642031", "latest"
        )
        expected = (
            f"{STAR_CDN_BASE}/GOES19/ABI/FD/GEOCOLOR/"
            "20260642031_GOES19-ABI-FD-GEOCOLOR-10848x10848.jpg"
        )
        assert url == expected

    def test_build_timestamped_url_conus_latest_still_5000x3000(self) -> None:
        """CONUS + resolution='latest' keeps its existing 5000x3000 behavior."""
        client = GOESClient()
        url = client.build_timestamped_url(
            "goes-19", "CONUS", "GEOCOLOR", "20260642031", "latest"
        )
        expected = (
            f"{STAR_CDN_BASE}/GOES19/ABI/CONUS/GEOCOLOR/"
            "20260642031_GOES19-ABI-CONUS-GEOCOLOR-5000x3000.jpg"
        )
        assert url == expected

    def test_build_timestamped_url_rejects_wrong_resolution_for_coverage(self) -> None:
        """A SECTOR-shaped resolution must be rejected for a CONUS timestamped URL."""
        client = GOESClient()
        with pytest.raises(ValueError, match="Unknown resolution"):
            client.build_timestamped_url(
                "goes-19", "CONUS", "GEOCOLOR", "20260642031", "2400x2400"
            )


class TestClientImageFetch:
    """Tests for GOESClient image download."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_image_success(self) -> None:
        """Successfully download image bytes."""
        client = GOESClient()
        test_bytes = load_fixture_bytes("test_image.jpg")
        url = f"{STAR_CDN_BASE}/GOES19/ABI/CONUS/GEOCOLOR/1250x750.jpg"

        respx.get(url).mock(
            return_value=httpx.Response(
                200, content=test_bytes, headers={"content-type": "image/jpeg"}
            )
        )

        result = await client.get_image(url)
        assert result == test_bytes
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_image_404(self) -> None:
        """404 response should raise GOESAPIError."""
        client = GOESClient()
        url = f"{STAR_CDN_BASE}/GOES19/ABI/CONUS/GEOCOLOR/nonexistent.jpg"

        respx.get(url).mock(return_value=httpx.Response(404))

        with pytest.raises(GOESAPIError, match="not found"):
            await client.get_image(url)
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_slider_times(self) -> None:
        """Fetch SLIDER timestamps returns correct list."""
        client = GOESClient()
        fixture = load_fixture("slider_latest_times.json")

        respx.get(url__startswith=SLIDER_BASE_URL).mock(
            return_value=httpx.Response(200, json=fixture)
        )

        timestamps = await client.get_slider_times(
            satellite="goes-19", sector="CONUS", product="GEOCOLOR", limit=5
        )

        assert len(timestamps) == 5
        assert timestamps[0] == "20260305202617"
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_slider_times_lowercase_fd_normalized(self) -> None:
        """sector='fd' must hit the same 'full_disk' SLIDER path as 'FD'."""
        client = GOESClient()
        fixture = load_fixture("slider_latest_times.json")

        route = respx.get(url__regex=r".*/goes-19/full_disk/geocolor/.*").mock(
            return_value=httpx.Response(200, json=fixture)
        )

        timestamps = await client.get_slider_times(
            satellite="goes-19", sector="fd", product="GEOCOLOR", limit=5
        )

        assert route.called
        assert len(timestamps) == 5
        await client.close()

    @pytest.mark.asyncio
    async def test_get_slider_times_rejects_regional_sector(self) -> None:
        """A regional SECTOR/xx sub-sector should raise before ever hitting SLIDER.

        Verified live: SLIDER only has 'conus'/'full_disk' for goes-19/18;
        'se'/'ne'/'car'/'taw'/'pr' (mapped from the old SLIDER_SECTORS) all
        404 there.
        """
        client = GOESClient()
        with pytest.raises(GOESAPIError, match="does not publish timestamps"):
            await client.get_slider_times(
                satellite="goes-19", sector="se", product="GEOCOLOR"
            )
        await client.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_get_image_rejects_small_body_even_with_image_content_type(
        self,
    ) -> None:
        """A tiny body should be rejected even if content-type says image/jpeg.

        This is the `and` -> `or` fix: a >1KB HTML error page with the wrong
        content-type, and a suspiciously small body with the *right*
        content-type (e.g. a truncated/placeholder response), should both be
        caught rather than returned as if they were a valid JPEG.
        """
        client = GOESClient()
        url = f"{STAR_CDN_BASE}/GOES19/ABI/CONUS/GEOCOLOR/1250x750.jpg"

        respx.get(url).mock(
            return_value=httpx.Response(
                200, content=b"tiny", headers={"content-type": "image/jpeg"}
            )
        )

        with pytest.raises(GOESAPIError, match="Expected image"):
            await client.get_image(url)
        await client.close()
