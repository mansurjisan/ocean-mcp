"""Unit tests for goes-mcp tool functions with mocked HTTP responses."""

import json
from unittest.mock import MagicMock

import httpx
import pytest
import respx

from goes_mcp.client import GOESClient, GOESAPIError
from goes_mcp.models import SLIDER_BASE_URL, STAR_CDN_BASE
from tests.conftest import load_fixture, load_fixture_bytes


@pytest.fixture
def coops_client() -> GOESClient:
    """Create a bare GOESClient."""
    return GOESClient()


@pytest.fixture
def ctx(coops_client: GOESClient) -> MagicMock:
    """Create a mock Context wired to the GOESClient."""
    mock_ctx = MagicMock()
    mock_ctx.request_context.lifespan_context = {"goes_client": coops_client}
    return mock_ctx


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
        """Fetch latest image with default format returns Image object."""
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
        """Fetch timestamped image with default format returns Image object."""
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
        """Fetch sector image with default format returns Image object."""
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
