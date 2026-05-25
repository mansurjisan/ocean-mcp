"""Async HTTP client for USGS Water Services API."""

import asyncio
import random
from typing import Any

import httpx

from .models import NWPS_GAUGE_URL, USGS_BASE_URL, USGS_PEAK_URL, USER_AGENT

# Transient responses worth retrying: rate-limit + the upstream/gateway 5xx
# family that NOAA/USGS endpoints intermittently emit under load.
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

    def __init__(self, max_retries: int = 2, backoff_factor: float = 0.5) -> None:
        self._client: httpx.AsyncClient | None = None
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": USER_AGENT},
                transport=RetryTransport(
                    max_retries=self._max_retries,
                    backoff_factor=self._backoff_factor,
                ),
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

    async def get_nwps_gauge(self, site_number: str) -> dict[str, Any] | None:
        """Fetch NWS/NWPS gauge metadata for a USGS site.

        The NWPS gauges endpoint accepts a USGS site number directly. Returns
        the parsed gauge JSON, or ``None`` if the site is not an NWS forecast
        point (404) or NWPS is unreachable — this augmentation must never make
        the flood-status tool fail, so all errors degrade to ``None``.
        """
        try:
            client = await self._get_client()
            response = await client.get(f"{NWPS_GAUGE_URL}/{site_number}")
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except Exception:
            return None

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
