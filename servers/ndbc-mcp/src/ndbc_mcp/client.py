"""Async HTTP client for NDBC realtime2 text files and activestations XML."""

import math
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any

import httpx

from .models import (
    ACTIVE_STATIONS_URL,
    MISSING_VALUES,
    REALTIME2_BASE,
    STATION_CACHE_TTL,
)


class NDBCAPIError(Exception):
    """Raised when an NDBC data request fails."""


class NDBCClient:
    """Client for NDBC realtime2 data and active-station metadata."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._station_cache: list[dict[str, Any]] = []
        self._cache_time: float = 0.0

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={"User-Agent": "ndbc-mcp/0.1.0"},
                follow_redirects=True,
            )
        return self._client

    # ------------------------------------------------------------------
    # Station metadata (activestations.xml)
    # ------------------------------------------------------------------

    async def get_active_stations(self) -> list[dict[str, Any]]:
        """Return cached or freshly-fetched active station list."""
        now = time.time()
        if self._station_cache and (now - self._cache_time) < STATION_CACHE_TTL:
            return self._station_cache

        client = await self._get_client()
        try:
            response = await client.get(ACTIVE_STATIONS_URL)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise NDBCAPIError(
                f"Failed to fetch active stations (HTTP {e.response.status_code})"
            ) from e
        except httpx.TimeoutException as e:
            raise NDBCAPIError("Timed out fetching active stations list") from e

        self._station_cache = _parse_active_stations_xml(response.text)
        self._cache_time = time.time()
        return self._station_cache

    async def get_station_metadata(self, station_id: str) -> dict[str, Any] | None:
        """Look up a single station from the active-stations cache."""
        stations = await self.get_active_stations()
        sid = station_id.upper()
        for s in stations:
            if s["id"] == sid:
                return s
        return None

    # ------------------------------------------------------------------
    # Realtime2 text data
    # ------------------------------------------------------------------

    async def fetch_realtime(self, station_id: str, extension: str = "txt") -> str:
        """Fetch a realtime2 text file for a station.

        Args:
            station_id: NDBC station ID (e.g. '41001').
            extension: File extension — 'txt', 'spec', 'cwind', 'ocean', etc.

        Returns:
            Raw text content of the file.
        """
        url = f"{REALTIME2_BASE}/{station_id.upper()}.{extension}"
        client = await self._get_client()
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise NDBCAPIError(
                    f"No {extension} data found for station {station_id.upper()}. "
                    f"Verify the station ID with ndbc_list_stations or ndbc_find_nearest_stations."
                ) from e
            raise NDBCAPIError(
                f"NDBC request failed (HTTP {e.response.status_code}) for {station_id.upper()}.{extension}"
            ) from e
        except httpx.TimeoutException as e:
            raise NDBCAPIError(
                f"Timed out fetching {extension} data for station {station_id.upper()}"
            ) from e
        return response.text

    async def get_observations(
        self,
        station_id: str,
        hours: int | None = None,
        extension: str = "txt",
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """Fetch and parse realtime2 observations.

        Returns:
            (columns, records) where columns is the header list and records
            is a list of dicts keyed by column name plus 'datetime'.
        """
        text = await self.fetch_realtime(station_id, extension)
        columns, records = parse_realtime_text(text)

        if hours is not None and hours > 0 and records:
            # Filter relative to the newest record, not wall-clock time.
            # Realtime2 files are sorted newest-first; the first record with a
            # valid datetime is the reference point.
            ref = None
            for r in records:
                if r.get("datetime"):
                    ref = r["datetime"]
                    break
            if ref is not None:
                cutoff = ref - timedelta(hours=hours)
                records = [
                    r for r in records if r.get("datetime") and r["datetime"] >= cutoff
                ]

        return columns, records

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# ----------------------------------------------------------------------
# XML parser for activestations.xml
# ----------------------------------------------------------------------


def _parse_active_stations_xml(xml_text: str) -> list[dict[str, Any]]:
    """Parse NDBC activestations.xml into a list of station dicts."""
    root = ET.fromstring(xml_text)
    stations: list[dict[str, Any]] = []
    for elem in root.iter("station"):
        attrib = elem.attrib
        station: dict[str, Any] = {
            "id": attrib.get("id", "").upper(),
            "lat": _safe_float(attrib.get("lat")),
            "lon": _safe_float(attrib.get("lon")),
            "name": attrib.get("name", ""),
            "owner": attrib.get("owner", ""),
            "type": attrib.get("type", ""),
            "pgm": attrib.get("pgm", ""),
            "met": attrib.get("met", ""),
            "currents": attrib.get("currents", ""),
            "waterquality": attrib.get("waterquality", ""),
            "dart": attrib.get("dart", ""),
        }
        stations.append(station)
    return stations


def _safe_float(val: str | None) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ----------------------------------------------------------------------
# Realtime2 fixed-width text parser
# ----------------------------------------------------------------------


def parse_realtime_text(text: str) -> tuple[list[str], list[dict[str, Any]]]:
    """Parse NDBC realtime2 fixed-width text into (columns, records).

    Handles .txt, .spec, .cwind, .ocean files — the column names are
    read from the first header line (starts with '#').
    """
    lines = text.strip().splitlines()
    if not lines:
        return [], []

    # Find header lines (start with '#')
    header_lines: list[str] = []
    data_start = 0
    for i, line in enumerate(lines):
        if line.startswith("#"):
            header_lines.append(line)
            data_start = i + 1
        else:
            break

    if not header_lines:
        return [], []

    # Column names from first header line
    columns = header_lines[0].lstrip("#").split()

    records: list[dict[str, Any]] = []
    for line in lines[data_start:]:
        parts = line.split()
        if len(parts) < 5:
            continue

        record: dict[str, Any] = {}

        # Build datetime from first 5 columns (YY MM DD hh mm)
        try:
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])
            hour = int(parts[3])
            minute = int(parts[4])
            record["datetime"] = datetime(year, month, day, hour, minute)
        except (ValueError, IndexError):
            record["datetime"] = None

        # Map remaining columns
        for j, col in enumerate(columns):
            if j < len(parts):
                raw = parts[j]
                if raw in MISSING_VALUES:
                    record[col] = None
                else:
                    try:
                        record[col] = float(raw)
                    except ValueError:
                        record[col] = raw
            else:
                record[col] = None

        records.append(record)

    return columns, records


# ----------------------------------------------------------------------
# Haversine distance
# ----------------------------------------------------------------------


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute distance in km between two lat/lon points."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ----------------------------------------------------------------------
# Error handler
# ----------------------------------------------------------------------


def handle_ndbc_error(e: Exception) -> str:
    """Format an exception into a user-friendly error message."""
    if isinstance(e, NDBCAPIError):
        return f"NDBC Error: {e}"
    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTP Error {e.response.status_code}: {e.response.reason_phrase}. NDBC may be temporarily unavailable."
    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. NDBC may be experiencing high load. Please try again."
    return f"Unexpected error: {type(e).__name__}: {e}"
