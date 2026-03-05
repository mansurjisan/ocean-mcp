"""Async HTTP client for NWS Weather.gov and Iowa Environmental Mesonet APIs."""

import csv
import io

import httpx
from typing import Any

from .models import NWS_API_BASE, IEM_BASE, USER_AGENT


class WindsAPIError(Exception):
    """Custom exception for Winds API errors."""

    pass


class WindsClient:
    """Async client for NWS and IEM APIs."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/geo+json",
                },
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
        return response.json()

    async def get_station(self, station_id: str) -> dict[str, Any]:
        """Get detailed metadata for a single station."""
        client = await self._get_client()
        url = f"{NWS_API_BASE}/stations/{station_id.upper()}"
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

    async def get_nearest_stations(
        self, lat: float, lon: float, limit: int = 5
    ) -> dict[str, Any]:
        """Find stations nearest to a coordinate."""
        client = await self._get_client()
        url = f"{NWS_API_BASE}/points/{lat},{lon}/stations"
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()
        # Trim to requested limit
        if "features" in data:
            data["features"] = data["features"][:limit]
        return data

    async def get_latest_observation(self, station_id: str) -> dict[str, Any]:
        """Get the most recent observation at a station."""
        client = await self._get_client()
        url = f"{NWS_API_BASE}/stations/{station_id.upper()}/observations/latest"
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

    async def get_observations(
        self, station_id: str, start: str, end: str
    ) -> dict[str, Any]:
        """Get observations for a time range (ISO 8601 strings)."""
        client = await self._get_client()
        url = f"{NWS_API_BASE}/stations/{station_id.upper()}/observations"
        params = {"start": start, "end": end}
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

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
        results = list(reader)
        return {"results": results}

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
