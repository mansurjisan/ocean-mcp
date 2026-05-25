"""Async HTTP client for NHC data sources."""

from __future__ import annotations

import asyncio
import random
import re
import time
from typing import Any

import httpx

from .utils import build_arcgis_query_url

# NHC data endpoints
NHC_SITE = "https://www.nhc.noaa.gov"
CURRENT_STORMS_URL = "https://www.nhc.noaa.gov/CurrentStorms.json"
ATCF_BDECK_URL = "https://ftp.nhc.noaa.gov/atcf/btk/b{basin}{number:02d}{year}.dat"

# HURDAT2 archive. NHC reissues these files every year with the latest season
# folded in and a new "data-through-YYYY" + revision date baked into the
# filename (e.g. hurdat2-1851-2025-02272026.txt). Hard-coding a dated filename
# silently drops the newest season and guarantees annual drift, so the live
# filename is discovered from the data index at call time; HURDAT2_URLS is the
# last-known-good fallback used only if discovery fails. Keep it current.
HURDAT2_INDEX_URL = "https://www.nhc.noaa.gov/data/"
HURDAT2_URLS = {
    "al": "https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-02272026.txt",
    "ep": "https://www.nhc.noaa.gov/data/hurdat/hurdat2-nepac-1949-2025-02272026.txt",
}
# Per-basin filename signature on the index page. The capture group is the
# "data through" year, used to pick the newest file.
_HURDAT2_PATTERNS = {
    "al": re.compile(r"/data/hurdat/(hurdat2-1851-(\d{4})-\d{4,8}\.txt)"),
    "ep": re.compile(r"/data/hurdat/(hurdat2-nepac-1949-(\d{4})-\d{4,8}\.txt)"),
}
# Cached HURDAT2 (resolved URL + multi-MB body) is refreshed past this age so
# a long-running MCP process picks up an annual reissue without a restart.
# 12 h bounds the staleness window while keeping refetches of a several-MB
# file rare (the archive changes ~once a year).
HURDAT2_CACHE_TTL_S = 12 * 60 * 60


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


class NHCAPIError(Exception):
    """Custom exception for NHC API errors."""

    pass


class NHCClient:
    """Async client for NHC data sources (CurrentStorms, ATCF, HURDAT2, ArcGIS)."""

    def __init__(self, max_retries: int = 2, backoff_factor: float = 0.5) -> None:
        self._client: httpx.AsyncClient | None = None
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        self._hurdat2_cache: dict[str, str] = {}
        self._hurdat2_url_cache: dict[str, str] = {}
        self._hurdat2_cache_time: dict[str, float] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=True,
                transport=RetryTransport(
                    max_retries=self._max_retries,
                    backoff_factor=self._backoff_factor,
                ),
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

    async def _resolve_hurdat2_url(self, lookup_basin: str) -> str:
        """Resolve the current HURDAT2 file URL for a basin.

        Scrapes the NHC data index for the newest ``hurdat2-…-YYYY-…txt``
        matching the basin signature so a new season is picked up
        automatically. Falls back to the last-known-good ``HURDAT2_URLS``
        entry if the index is unreachable or unparseable — discovery must
        never make the tool fail when a usable URL is known.

        Args:
            lookup_basin: 'al' or 'ep' (already mapped; 'cp' uses 'ep').

        Returns:
            Absolute URL string.
        """
        if lookup_basin in self._hurdat2_url_cache:
            return self._hurdat2_url_cache[lookup_basin]

        fallback = HURDAT2_URLS.get(lookup_basin)
        if not fallback:
            raise ValueError(f"No HURDAT2 data available for basin '{lookup_basin}'.")

        pattern = _HURDAT2_PATTERNS.get(lookup_basin)
        resolved = fallback
        if pattern is not None:
            try:
                client = await self._get_client()
                response = await client.get(HURDAT2_INDEX_URL)
                response.raise_for_status()
                matches = pattern.findall(response.text)
                if matches:
                    # matches: list of (filename, year); pick the newest year.
                    fname, _ = max(matches, key=lambda m: int(m[1]))
                    resolved = f"{NHC_SITE}/data/hurdat/{fname}"
            except Exception:
                # Any failure (network, HTTP, parse) → keep the fallback.
                resolved = fallback

        self._hurdat2_url_cache[lookup_basin] = resolved
        return resolved

    async def get_hurdat2(self, basin: str) -> str:
        """Fetch HURDAT2 data for a basin, with in-memory caching.

        The file URL is resolved from the live NHC data index (newest
        season), so this stays current across annual reissues without a
        code change.

        Args:
            basin: Basin code ('al' or 'ep'). 'cp' falls back to 'ep'.

        Returns:
            Raw HURDAT2 text content.
        """
        # Central Pacific storms are in the East Pacific HURDAT2 file
        lookup_basin = "ep" if basin == "cp" else basin

        cached_at = self._hurdat2_cache_time.get(lookup_basin)
        if (
            lookup_basin in self._hurdat2_cache
            and cached_at is not None
            and (time.time() - cached_at) < HURDAT2_CACHE_TTL_S
        ):
            return self._hurdat2_cache[lookup_basin]

        # Stale (or first fetch): drop the resolved-URL cache too so an annual
        # reissue under a *new* filename is re-discovered, not just refetched.
        self._hurdat2_url_cache.pop(lookup_basin, None)
        url = await self._resolve_hurdat2_url(lookup_basin)

        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        text = response.text
        self._hurdat2_cache[lookup_basin] = text
        self._hurdat2_cache_time[lookup_basin] = time.time()
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
