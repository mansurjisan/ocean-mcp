"""Async HTTP client for NWS Weather.gov and Iowa Environmental Mesonet APIs."""

import asyncio
import csv
import io
import random

import httpx
from typing import Any

from .models import NWS_API_BASE, IEM_BASE, USER_AGENT


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


class WindsAPIError(Exception):
    """Raised for the server's own semantic errors — e.g. a malformed
    response body — as distinct from httpx.HTTPStatusError/TimeoutException,
    which are handled separately by handle_winds_error()."""


def _parse_nws_json(response: httpx.Response, context: str) -> dict[str, Any]:
    """Parse a NWS JSON response, raising WindsAPIError on a malformed body.

    httpx's ``raise_for_status()`` only catches bad status codes; it says
    nothing about the body. A degraded NWS gateway can still return 200
    with a truncated or non-JSON (e.g. HTML error) body, which would
    otherwise surface as a raw json.JSONDecodeError — this wraps that as
    the server's own semantic error instead.
    """
    try:
        return response.json()
    except ValueError as e:
        raise WindsAPIError(
            f"Malformed response from NWS while fetching {context}."
        ) from e


class WindsClient:
    """Async client for NWS and IEM APIs."""

    def __init__(self, max_retries: int = 2, backoff_factor: float = 0.5) -> None:
        self._client: httpx.AsyncClient | None = None
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/geo+json",
                },
                transport=RetryTransport(
                    max_retries=self._max_retries,
                    backoff_factor=self._backoff_factor,
                ),
            )
        return self._client

    # -----------------------------------------------------------------------
    # NWS Weather.gov API methods
    # -----------------------------------------------------------------------

    async def get_stations_by_state(
        self, state: str, limit: int = 50
    ) -> dict[str, Any]:
        """List NWS stations filtered by state code."""
        client = await self._get_client()
        url = f"{NWS_API_BASE}/stations"
        params: dict[str, Any] = {"state": state.upper(), "limit": limit}
        response = await client.get(url, params=params)
        response.raise_for_status()
        return _parse_nws_json(response, f"stations for state {state.upper()}")

    async def get_station(self, station_id: str) -> dict[str, Any]:
        """Get detailed metadata for a single station."""
        client = await self._get_client()
        url = f"{NWS_API_BASE}/stations/{station_id.upper()}"
        response = await client.get(url)
        response.raise_for_status()
        return _parse_nws_json(response, f"station {station_id.upper()}")

    async def get_nearest_stations(self, lat: float, lon: float) -> dict[str, Any]:
        """Find stations nearest to a coordinate.

        Returns the full, untrimmed NWS result — callers apply their own
        limit so they can report how many were available before trimming.
        """
        client = await self._get_client()
        url = f"{NWS_API_BASE}/points/{lat},{lon}/stations"
        response = await client.get(url)
        response.raise_for_status()
        return _parse_nws_json(response, f"nearest stations to ({lat}, {lon})")

    async def get_latest_observation(self, station_id: str) -> dict[str, Any]:
        """Get the most recent observation at a station."""
        client = await self._get_client()
        url = f"{NWS_API_BASE}/stations/{station_id.upper()}/observations/latest"
        response = await client.get(url)
        response.raise_for_status()
        return _parse_nws_json(response, f"latest observation for {station_id.upper()}")

    async def get_observations(
        self, station_id: str, start: str, end: str
    ) -> dict[str, Any]:
        """Get observations for a time range (ISO 8601 strings)."""
        client = await self._get_client()
        url = f"{NWS_API_BASE}/stations/{station_id.upper()}/observations"
        params = {"start": start, "end": end}
        response = await client.get(url, params=params)
        response.raise_for_status()
        return _parse_nws_json(response, f"observations for {station_id.upper()}")

    # -----------------------------------------------------------------------
    # Iowa Environmental Mesonet (IEM) API methods
    # -----------------------------------------------------------------------

    async def get_iem_history(
        self, station: str, start_date: str, end_date: str
    ) -> dict[str, Any]:
        """Fetch historical ASOS data from the IEM archive.

        station: 3-or-4 char station code (K prefix stripped automatically).
        start_date/end_date: YYYY-MM-DD format.
        Returns dict with "results" key containing list of observation dicts.
        """
        # IEM uses 3-char FAA codes; strip leading K if present
        faa_code = station.upper()
        if len(faa_code) == 4 and faa_code.startswith("K"):
            faa_code = faa_code[1:]

        # Parse dates
        parts_start = start_date.split("-")
        parts_end = end_date.split("-")

        client = await self._get_client()
        url = f"{IEM_BASE}/cgi-bin/request/asos.py"
        params: dict[str, Any] = {
            "station": faa_code,
            "data": "all",
            "tz": "UTC",
            "format": "onlycomma",
            "latlon": "yes",
            "year1": parts_start[0],
            "month1": parts_start[1],
            "day1": parts_start[2],
            "year2": parts_end[0],
            "month2": parts_end[1],
            "day2": parts_end[2],
        }

        response = await client.get(
            url,
            params=params,
            headers={"Accept": "text/plain"},
        )
        response.raise_for_status()
        return self._parse_iem_csv(response.text)

    @staticmethod
    def _parse_iem_csv(text: str) -> dict[str, Any]:
        """Parse IEM ASOS CSV response into a dict with a 'results' list."""
        # Skip comment/debug lines starting with #
        lines = [line for line in text.splitlines() if not line.startswith("#")]
        if not lines:
            return {"results": []}
        content = "\n".join(lines)
        reader = csv.DictReader(io.StringIO(content))
        if reader.fieldnames is None or "station" not in reader.fieldnames:
            # A degraded IEM backend can return an error/HTML body with a
            # 200 status; that parses as CSV with no recognizable header
            # instead of raising, so check the header shape explicitly.
            raise WindsAPIError(
                "Malformed response from IEM ASOS archive (unexpected CSV format)."
            )
        results = list(reader)
        return {"results": results}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def handle_winds_error(e: Exception) -> str:
    """Format an exception into a user-friendly error message.

    Distinguishes the server's own semantic errors (WindsAPIError), an
    upstream HTTP status error, and a timeout, falling back to a typed
    generic — never a bare exception repr. Shared by both tools/stations.py
    and tools/observations.py so the two don't drift out of sync again.
    """
    if isinstance(e, WindsAPIError):
        return f"Winds Error: {e}"

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return (
                "Error: Station not found. Verify the station ID (ICAO format, "
                "e.g., KJFK) using winds_list_stations or "
                "winds_find_nearest_stations."
            )
        return (
            f"HTTP Error {status}: {e.response.reason_phrase}. The NWS/IEM API "
            "may be temporarily unavailable."
        )

    if isinstance(e, httpx.TimeoutException):
        return (
            "Error: Request timed out. The NWS/IEM API may be experiencing "
            "high load. Please try again."
        )

    return f"Unexpected error: {type(e).__name__}: {e}"
