"""Async HTTP client for NHC reconnaissance data sources."""

from __future__ import annotations

import httpx

from .models import ATCF_FIX_BASE, NHC_RECON_ARCHIVE_BASE, PRODUCT_DIRS


class ReconAPIError(Exception):
    """Custom exception for reconnaissance data access errors."""

    pass


class ReconClient:
    """Async client for NHC reconnaissance archive and ATCF fix data."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=True,
            )
        return self._client

    async def fetch_text(self, url: str) -> str:
        """Fetch text content from a URL.

        Args:
            url: Full URL to fetch.

        Returns:
            Response text content.

        Raises:
            httpx.HTTPStatusError: On non-2xx responses.
        """
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        return response.text

    async def list_directory(self, url: str) -> str:
        """Fetch an Apache-style HTML directory listing.

        Args:
            url: Directory URL (must end with /).

        Returns:
            Raw HTML of the directory listing.
        """
        if not url.endswith("/"):
            url += "/"
        return await self.fetch_text(url)

    def build_archive_dir_url(self, year: int, product: str, basin: str) -> str:
        """Build a URL for a product directory in the NHC recon archive.

        Args:
            year: 4-digit year.
            product: Product type ('hdob', 'vdm', 'dropsonde').
            basin: Basin code ('al', 'ep').

        Returns:
            Full URL to the product directory.

        Raises:
            ValueError: If the product/basin combination is invalid.
        """
        # CP basin falls back to EP for recon products
        lookup_basin = "ep" if basin == "cp" else basin
        key = (product, lookup_basin)
        wmo_dir = PRODUCT_DIRS.get(key)
        if not wmo_dir:
            raise ValueError(
                f"No archive directory for product='{product}', basin='{basin}'. "
                f"Valid combinations: {list(PRODUCT_DIRS.keys())}"
            )
        return f"{NHC_RECON_ARCHIVE_BASE}/{year}/{wmo_dir}/"

    def build_atcf_fdeck_url(self, basin: str, storm_number: int, year: int) -> str:
        """Build a URL for an ATCF f-deck fix file.

        Args:
            basin: Basin code ('al', 'ep', 'cp').
            storm_number: Storm number within the season.
            year: 4-digit year.

        Returns:
            Full URL to the f-deck file.
        """
        return f"{ATCF_FIX_BASE}/f{basin}{storm_number:02d}{year}.dat"

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
