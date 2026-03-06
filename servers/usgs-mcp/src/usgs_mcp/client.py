"""Async HTTP client for USGS Water Services API."""

from typing import Any

import httpx

from .models import USGS_BASE_URL, USGS_PEAK_URL, USER_AGENT


class USGSAPIError(Exception):
    """Custom exception for USGS API errors."""

    pass


def parse_rdb(text: str) -> list[dict[str, str]]:
    """Parse USGS RDB tab-delimited format to list of dicts.

    RDB format: # comment lines, then header row, then data type row
    (5s, 15n, etc.), then data rows.
    """
    lines = [line for line in text.strip().split("\n") if not line.startswith("#")]
    if len(lines) < 2:
        return []
    headers = lines[0].split("\t")
    # Skip lines[1] — data type definitions (e.g., "5s\t15s\t20d")
    rows = []
    for line in lines[2:]:
        if not line.strip():
            continue
        vals = line.split("\t")
        rows.append(dict(zip(headers, vals)))
    return rows


class USGSClient:
    """Async client for USGS Water Services API."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": USER_AGENT},
            )
        return self._client

    async def get_json(self, endpoint: str, params: dict[str, Any]) -> dict:
        """Fetch JSON from IV/DV endpoints."""
        params["format"] = "json"
        client = await self._get_client()
        response = await client.get(f"{USGS_BASE_URL}/{endpoint}/", params=params)
        response.raise_for_status()
        return response.json()

    async def get_rdb(
        self, endpoint: str, params: dict[str, Any]
    ) -> list[dict[str, str]]:
        """Fetch RDB (tab-delimited) from site/stat endpoints."""
        params["format"] = "rdb"
        client = await self._get_client()
        response = await client.get(f"{USGS_BASE_URL}/{endpoint}/", params=params)
        response.raise_for_status()
        return parse_rdb(response.text)

    async def get_peak(self, params: dict[str, Any]) -> list[dict[str, str]]:
        """Fetch peak streamflow RDB from nwis.waterdata.usgs.gov."""
        params["format"] = "rdb"
        client = await self._get_client()
        response = await client.get(USGS_PEAK_URL, params=params)
        response.raise_for_status()
        return parse_rdb(response.text)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
