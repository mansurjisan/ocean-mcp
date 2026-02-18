"""Async HTTP client for ERDDAP servers."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx


class ERDDAPClient:
    """Async client for ERDDAP REST API."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=True,
            )
        return self._client

    async def _get_json(self, url: str) -> dict:
        """Fetch a URL and return parsed JSON, handling ERDDAP error responses."""
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "html" in content_type and "json" not in content_type:
            raise ValueError(
                f"ERDDAP returned HTML instead of JSON. This usually means an error occurred. "
                f"URL: {url}"
            )

        return response.json()

    async def search(
        self,
        server_url: str,
        search_for: str,
        page: int = 1,
        items_per_page: int = 20,
    ) -> dict:
        """Search for datasets on an ERDDAP server.

        Args:
            server_url: Base ERDDAP server URL.
            search_for: Free-text search terms.
            page: Page number (1-indexed).
            items_per_page: Results per page.

        Returns:
            Raw ERDDAP JSON response.
        """
        encoded_search = quote(search_for)
        url = (
            f"{server_url}/search/index.json"
            f"?searchFor={encoded_search}"
            f"&page={page}"
            f"&itemsPerPage={items_per_page}"
        )
        return await self._get_json(url)

    async def get_info(self, server_url: str, dataset_id: str) -> dict:
        """Get dataset metadata/info.

        Args:
            server_url: Base ERDDAP server URL.
            dataset_id: ERDDAP dataset identifier.

        Returns:
            Raw ERDDAP JSON response.
        """
        url = f"{server_url}/info/{dataset_id}/index.json"
        return await self._get_json(url)

    async def get_tabledap(
        self,
        server_url: str,
        dataset_id: str,
        query: str,
    ) -> dict:
        """Fetch data from a tabledap dataset.

        Args:
            server_url: Base ERDDAP server URL.
            dataset_id: ERDDAP dataset identifier.
            query: Pre-built query string (variables & constraints).

        Returns:
            Raw ERDDAP JSON response.
        """
        url = f"{server_url}/tabledap/{dataset_id}.json"
        if query:
            url += f"?{query}"
        return await self._get_json(url)

    async def get_griddap(
        self,
        server_url: str,
        dataset_id: str,
        query: str,
    ) -> dict:
        """Fetch data from a griddap dataset.

        Args:
            server_url: Base ERDDAP server URL.
            dataset_id: ERDDAP dataset identifier.
            query: Pre-built griddap query with bracket notation.

        Returns:
            Raw ERDDAP JSON response.
        """
        url = f"{server_url}/griddap/{dataset_id}.json?{query}"
        return await self._get_json(url)

    async def get_all_datasets(
        self,
        server_url: str,
        query: str = "",
    ) -> dict:
        """List all datasets on an ERDDAP server.

        Args:
            server_url: Base ERDDAP server URL.
            query: Optional query string for filtering.

        Returns:
            Raw ERDDAP JSON response.
        """
        url = f"{server_url}/tabledap/allDatasets.json"
        if query:
            url += f"?{query}"
        return await self._get_json(url)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
