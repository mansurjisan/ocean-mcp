"""Async HTTP client for GOES satellite imagery APIs."""

import re

import httpx

from .models import (
    SLIDER_BASE_URL,
    SLIDER_PRODUCTS,
    SLIDER_SATELLITES,
    SLIDER_SECTORS,
    STAR_CDN_BASE,
    satellite_key_to_id,
    validate_coverage,
    validate_product,
    validate_resolution,
    validate_sector,
)


class GOESAPIError(Exception):
    """Custom exception for GOES API errors."""


class GOESClient:
    """Async client for NOAA STAR CDN and RAMMB/CIRA SLIDER APIs."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # --- URL builders ---

    def build_latest_url(
        self,
        satellite: str,
        coverage: str,
        product: str,
        resolution: str,
    ) -> str:
        """Build URL for the latest image on STAR CDN.

        Args:
            satellite: Satellite key (e.g., 'goes-19').
            coverage: Coverage code (e.g., 'CONUS', 'FD').
            product: Product code (e.g., 'GEOCOLOR', '13').
            resolution: Resolution key (e.g., '1250x750', 'thumbnail').

        Returns:
            Full URL to the latest image.
        """
        sat_id = satellite_key_to_id(satellite)
        cov_path = validate_coverage(coverage)
        product = validate_product(product)
        filename = validate_resolution(resolution)
        return f"{STAR_CDN_BASE}/{sat_id}/ABI/{cov_path}/{product}/{filename}"

    def build_sector_url(
        self,
        satellite: str,
        sector: str,
        product: str,
        resolution: str,
    ) -> str:
        """Build URL for the latest sector image on STAR CDN.

        Args:
            satellite: Satellite key (e.g., 'goes-19').
            sector: Sector code (e.g., 'se', 'ne', 'car').
            product: Product code (e.g., 'GEOCOLOR', '13').
            resolution: Resolution key (e.g., '1250x750', 'thumbnail').

        Returns:
            Full URL to the latest sector image.
        """
        sat_id = satellite_key_to_id(satellite)
        sector_path = validate_sector(sector)
        product = validate_product(product)
        filename = validate_resolution(resolution)
        return f"{STAR_CDN_BASE}/{sat_id}/ABI/{sector_path}/{product}/{filename}"

    def build_timestamped_url(
        self,
        satellite: str,
        coverage: str,
        product: str,
        timestamp: str,
        resolution: str,
    ) -> str:
        """Build URL for a timestamped image on STAR CDN.

        Args:
            satellite: Satellite key (e.g., 'goes-19').
            coverage: Coverage code (e.g., 'CONUS', 'FD').
            product: Product code (e.g., 'GEOCOLOR', '13').
            timestamp: Timestamp in YYYYDDDHHmm format.
            resolution: Resolution key (e.g., '1250x750').

        Returns:
            Full URL to the timestamped image.
        """
        sat_id = satellite_key_to_id(satellite)
        cov_path = validate_coverage(coverage)
        product = validate_product(product)

        # Validate timestamp format (YYYYDDDHHmm = 11 digits)
        if not re.match(r"^\d{11}$", timestamp):
            raise ValueError(
                f"Invalid timestamp '{timestamp}'. "
                "Expected format: YYYYDDDHHmm (11 digits, DDD=day-of-year)"
            )

        # Get pixel dimensions from resolution key
        res_key = resolution.lower().strip()
        if res_key == "thumbnail":
            w, h = "416", "250"
        elif res_key == "latest":
            w, h = "5000", "3000"
        elif "x" in res_key:
            w, h = res_key.split("x")
        else:
            raise ValueError(
                f"Cannot determine pixel dimensions for resolution '{resolution}'"
            )

        filename = f"{timestamp}_GOES{sat_id[-2:]}-ABI-{cov_path}-{product}-{w}x{h}.jpg"
        return f"{STAR_CDN_BASE}/{sat_id}/ABI/{cov_path}/{product}/{filename}"

    # --- Data fetchers ---

    async def get_image(self, url: str) -> bytes:
        """Download an image from STAR CDN.

        Args:
            url: Full URL to the image.

        Returns:
            Raw JPEG bytes.

        Raises:
            GOESAPIError: If the download fails.
        """
        client = await self._get_client()
        try:
            response = await client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "image" not in content_type and len(response.content) < 1000:
                raise GOESAPIError(
                    f"Expected image but got {content_type}. "
                    "The image may not be available at this time."
                )
            return response.content
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise GOESAPIError(
                    f"Image not found at {url}. "
                    "The timestamp may be too old or the product unavailable."
                ) from e
            raise GOESAPIError(
                f"HTTP {e.response.status_code} fetching image: {e}"
            ) from e
        except httpx.TimeoutException as e:
            raise GOESAPIError(f"Timeout downloading image from {url}") from e

    async def get_slider_times(
        self,
        satellite: str = "goes-19",
        sector: str = "CONUS",
        product: str = "GEOCOLOR",
        limit: int = 10,
    ) -> list[str]:
        """Fetch latest available timestamps from RAMMB/CIRA SLIDER.

        Args:
            satellite: Satellite key (e.g., 'goes-19').
            sector: Sector or coverage code (e.g., 'CONUS', 'se').
            product: Product code (e.g., 'GEOCOLOR', '13').
            limit: Maximum number of timestamps to return.

        Returns:
            List of timestamps in YYYYMMDDHHmmss format, most recent first.
        """
        sat_key = satellite.lower().strip()
        slider_sat = SLIDER_SATELLITES.get(sat_key, sat_key)

        # Map sector to SLIDER format
        sector_clean = sector.lower().strip()
        slider_sector = SLIDER_SECTORS.get(
            sector, SLIDER_SECTORS.get(sector_clean, sector_clean)
        )

        # Map product to SLIDER format
        product_clean = validate_product(product)
        slider_product = SLIDER_PRODUCTS.get(product_clean, product_clean.lower())

        url = (
            f"{SLIDER_BASE_URL}/data/json/"
            f"{slider_sat}/{slider_sector}/{slider_product}/latest_times.json"
        )

        client = await self._get_client()
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            timestamps = data.get("timestamps_int", [])
            # Convert integers to strings
            str_timestamps = [str(ts) for ts in timestamps]
            return str_timestamps[:limit]
        except httpx.HTTPStatusError as e:
            raise GOESAPIError(
                f"Failed to fetch timestamps from SLIDER: HTTP {e.response.status_code}"
            ) from e
        except (httpx.TimeoutException, Exception) as e:
            raise GOESAPIError(f"Error fetching SLIDER timestamps: {e}") from e
