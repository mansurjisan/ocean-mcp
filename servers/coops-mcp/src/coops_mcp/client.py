"""Shared async HTTP client for CO-OPS APIs."""

import httpx
from typing import Any

DATA_API_BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
METADATA_API_BASE = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi"
DERIVED_API_BASE = "https://api.tidesandcurrents.noaa.gov/dpapi/prod/webapi"

APPLICATION_NAME = "coops_mcp"


class COOPSAPIError(Exception):
    """Custom exception for CO-OPS API errors."""

    pass


class COOPSClient:
    """Async client for CO-OPS APIs."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def fetch_data(self, params: dict[str, Any]) -> dict:
        """Fetch from the Data API (datagetter).

        Automatically sets format=json and application=coops_mcp.
        Raises COOPSAPIError if the API returns an error in the JSON body.
        """
        params["format"] = "json"
        params["application"] = APPLICATION_NAME
        client = await self._get_client()
        response = await client.get(DATA_API_BASE, params=params)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise COOPSAPIError(data["error"].get("message", "Unknown API error"))
        return data

    async def fetch_metadata(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict:
        """Fetch from the Metadata API."""
        url = f"{METADATA_API_BASE}/{path}"
        client = await self._get_client()
        response = await client.get(url, params=params or {})
        response.raise_for_status()
        return response.json()

    async def fetch_derived(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict:
        """Fetch from the Derived Product API."""
        url = f"{DERIVED_API_BASE}/{path}"
        client = await self._get_client()
        response = await client.get(url, params=params or {})
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
