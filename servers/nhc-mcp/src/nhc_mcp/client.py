"""Async HTTP client for NHC data sources."""

from __future__ import annotations

from typing import Any

import httpx

from .utils import build_arcgis_query_url

# NHC data endpoints
CURRENT_STORMS_URL = "https://www.nhc.noaa.gov/CurrentStorms.json"
ATCF_BDECK_URL = "https://ftp.nhc.noaa.gov/atcf/btk/b{basin}{number:02d}{year}.dat"
HURDAT2_URLS = {
    "al": "https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2024-040425.txt",
    "ep": "https://www.nhc.noaa.gov/data/hurdat/hurdat2-nepac-1949-2024-031725.txt",
}


class NHCAPIError(Exception):
    """Custom exception for NHC API errors."""

    pass


class NHCClient:
    """Async client for NHC data sources (CurrentStorms, ATCF, HURDAT2, ArcGIS)."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._hurdat2_cache: dict[str, str] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=True,
            )
        return self._client

    async def get_active_storms(self) -> list[dict]:
        """Fetch currently active tropical cyclones from CurrentStorms.json.

        Returns:
            List of active storm dicts. May be empty outside hurricane season.
        """
        client = await self._get_client()
        response = await client.get(CURRENT_STORMS_URL)
        response.raise_for_status()
        data = response.json()
        return data.get("activeStorms", [])

    async def get_best_track_atcf(self, basin: str, number: int, year: int) -> str:
        """Fetch ATCF B-deck best track data for a specific storm.

        Args:
            basin: Basin code ('al', 'ep', 'cp').
            number: Storm number within the season.
            year: 4-digit year.

        Returns:
            Raw B-deck text content.

        Raises:
            httpx.HTTPStatusError: If the file doesn't exist (404).
        """
        url = ATCF_BDECK_URL.format(basin=basin, number=number, year=year)
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        return response.text

    async def get_hurdat2(self, basin: str) -> str:
        """Fetch HURDAT2 data for a basin, with in-memory caching.

        Args:
            basin: Basin code ('al' or 'ep'). 'cp' falls back to 'ep'.

        Returns:
            Raw HURDAT2 text content.
        """
        # Central Pacific storms are in the East Pacific HURDAT2 file
        lookup_basin = "ep" if basin == "cp" else basin

        if lookup_basin in self._hurdat2_cache:
            return self._hurdat2_cache[lookup_basin]

        url = HURDAT2_URLS.get(lookup_basin)
        if not url:
            raise ValueError(f"No HURDAT2 data available for basin '{basin}'.")

        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        text = response.text
        self._hurdat2_cache[lookup_basin] = text
        return text

    async def query_arcgis_layer(
        self,
        layer_id: int,
        where: str = "1=1",
    ) -> dict[str, Any]:
        """Query an ArcGIS MapServer layer.

        Args:
            layer_id: MapServer layer ID.
            where: SQL WHERE clause.

        Returns:
            ArcGIS JSON response with features.
        """
        url = build_arcgis_query_url(layer_id, where=where)
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            error = data["error"]
            msg = error.get("message", "Unknown ArcGIS error")
            raise NHCAPIError(f"ArcGIS error: {msg}")

        return data

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
