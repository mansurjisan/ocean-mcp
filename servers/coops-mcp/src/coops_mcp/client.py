"""Shared async HTTP client for CO-OPS APIs."""

import asyncio
import random

import httpx
from typing import Any

DATA_API_BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
METADATA_API_BASE = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi"
DERIVED_API_BASE = "https://api.tidesandcurrents.noaa.gov/dpapi/prod/webapi"

APPLICATION_NAME = "coops_mcp"


# Transient responses worth retrying: rate-limit + the upstream/gateway 5xx
# family that NOAA endpoints intermittently emit under load.
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


class RetryTransport(httpx.AsyncHTTPTransport):
    """AsyncHTTPTransport that retries idempotent GETs on transient failures.

    httpx's built-in ``retries=`` covers only connection errors; this also
    retries transient HTTP 5xx/429 and timeouts (read included) with
    exponential backoff plus jitter. These servers are read-only and issue
    only GETs, which are safe to replay; non-GET requests and non-transient
    responses pass straight through. Set ``backoff_factor=0`` to retry with
    no delay (used by the test suite).
    """

    def __init__(
        self,
        *args: Any,
        max_retries: int = 2,
        backoff_factor: float = 0.5,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method != "GET":
            return await super().handle_async_request(request)

        last_exc: httpx.TransportError | None = None
        for attempt in range(self._max_retries + 1):
            if attempt:
                delay = self._backoff_factor * (2 ** (attempt - 1))
                await asyncio.sleep(delay + random.uniform(0, delay / 2))
            try:
                response = await super().handle_async_request(request)
            except httpx.TransportError as exc:
                last_exc = exc
                continue
            if response.status_code in _RETRY_STATUS and attempt < self._max_retries:
                await response.aclose()
                continue
            return response
        assert last_exc is not None  # loop ran at least once
        raise last_exc


class COOPSAPIError(Exception):
    """Custom exception for CO-OPS API errors."""

    pass


class COOPSClient:
    """Async client for CO-OPS APIs."""

    def __init__(self, max_retries: int = 2, backoff_factor: float = 0.5) -> None:
        self._client: httpx.AsyncClient | None = None
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                transport=RetryTransport(
                    max_retries=self._max_retries,
                    backoff_factor=self._backoff_factor,
                ),
            )
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
