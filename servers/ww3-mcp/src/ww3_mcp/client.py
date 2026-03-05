"""Async HTTP client for GFS-Wave GRIB2 data and NDBC buoy observations."""

from __future__ import annotations

import tempfile
from pathlib import Path

import httpx

from .models import (
    GFS_S3_BASE,
    GRIB_VAR_FILTER,
    NDBC_HISTORY_BASE,
    NDBC_REALTIME_BASE,
    NDBC_STATIONS_URL,
    NOMADS_GRIB_FILTER_BASE,
    WAVE_GRIDS,
)


class WW3APIError(Exception):
    """Custom exception for WW3/NDBC API errors."""

    pass


class WW3Client:
    """Async client for GFS-Wave GRIB2 data and NDBC buoy observations."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=120.0,
                follow_redirects=True,
            )
        return self._client

    # ------------------------------------------------------------------
    # GFS-Wave GRIB2 via NOMADS Grib Filter
    # ------------------------------------------------------------------

    def build_grib_filter_url(
        self,
        grid: str,
        date: str,
        cycle: str,
        fhour: int,
        variables: list[str] | None = None,
        lat_range: tuple[float, float] | None = None,
        lon_range: tuple[float, float] | None = None,
    ) -> str:
        """Build a NOMADS Grib Filter URL for subsetting GFS-Wave GRIB2 data.

        Args:
            grid: Grid key (e.g., 'global.0p25').
            date: Date in YYYYMMDD format.
            cycle: Cycle hour (e.g., '00', '06', '12', '18').
            fhour: Forecast hour (e.g., 0, 6, 12, ...).
            variables: List of GRIB variable names to request (e.g., ['HTSGW', 'PERPW']).
            lat_range: (south, north) latitude bounds for subsetting.
            lon_range: (west, east) longitude bounds for subsetting (0-360 convention).

        Returns:
            Full URL for the NOMADS grib filter request.
        """
        grid_info = WAVE_GRIDS.get(grid, {})
        file_name = grid_info.get("file_template", "").format(cycle=cycle, fhour=fhour)
        dir_path = grid_info.get("dir_template", "").format(date=date, cycle=cycle)

        params = [f"file={file_name}", f"dir=%2F{dir_path}"]

        # Add variable filters
        if variables:
            for var in variables:
                filter_key = GRIB_VAR_FILTER.get(var)
                if filter_key:
                    params.append(f"{filter_key}=on")
        else:
            params.append("all_var=on")

        # Subsetting
        if lat_range:
            params.append("subregion=")
            params.append(f"toplat={lat_range[1]}")
            params.append(f"bottomlat={lat_range[0]}")
        if lon_range:
            if "subregion=" not in params:
                params.append("subregion=")
            params.append(f"leftlon={lon_range[0]}")
            params.append(f"rightlon={lon_range[1]}")

        # Surface level
        params.append("lev_surface=on")

        return f"{NOMADS_GRIB_FILTER_BASE}?{'&'.join(params)}"

    async def download_grib_subset(
        self,
        grid: str,
        date: str,
        cycle: str,
        fhour: int,
        variables: list[str] | None = None,
        lat_range: tuple[float, float] | None = None,
        lon_range: tuple[float, float] | None = None,
    ) -> Path:
        """Download a subsetted GRIB2 file from NOMADS.

        Args:
            grid: Grid key (e.g., 'global.0p25').
            date: Date in YYYYMMDD format.
            cycle: Cycle hour (e.g., '00').
            fhour: Forecast hour.
            variables: GRIB variable names to subset.
            lat_range: Latitude bounds (south, north).
            lon_range: Longitude bounds (west, east) in 0-360.

        Returns:
            Path to the temporary GRIB2 file. Caller must delete.
        """
        url = self.build_grib_filter_url(
            grid, date, cycle, fhour, variables, lat_range, lon_range
        )
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()

        tmp = tempfile.NamedTemporaryFile(suffix=".grib2", delete=False)
        tmp.write(response.content)
        tmp.close()
        return Path(tmp.name)

    # ------------------------------------------------------------------
    # GFS-Wave cycle availability (S3 HEAD)
    # ------------------------------------------------------------------

    def build_s3_grib_url(self, grid: str, date: str, cycle: str, fhour: int) -> str:
        """Build an S3 URL for a GFS-Wave GRIB2 file (for HEAD checks)."""
        grid_info = WAVE_GRIDS.get(grid, {})
        file_name = grid_info.get("file_template", "").format(cycle=cycle, fhour=fhour)
        dir_path = grid_info.get("dir_template", "").format(date=date, cycle=cycle)
        return f"{GFS_S3_BASE}/{dir_path}/{file_name}"

    async def check_grib_exists(self, url: str) -> bool:
        """Check if a GRIB2 file exists using HTTP HEAD."""
        client = await self._get_client()
        try:
            response = await client.head(url)
            return response.status_code == 200
        except Exception:
            return False

    async def resolve_latest_cycle(
        self,
        grid: str = "global.0p25",
        num_days: int = 2,
    ) -> tuple[str, str] | None:
        """Find the latest available GFS-Wave cycle on S3.

        Args:
            grid: Grid key to check.
            num_days: Number of past days to search.

        Returns:
            (date_str, cycle_str) tuple, or None if not found.
        """
        from datetime import datetime, timedelta, timezone

        grid_info = WAVE_GRIDS.get(grid, {})
        cycles = grid_info.get("cycles", ["00", "06", "12", "18"])
        cycles_desc = sorted(cycles, reverse=True)

        today = datetime.now(timezone.utc)
        for day_offset in range(num_days):
            date = today - timedelta(days=day_offset)
            date_str = date.strftime("%Y%m%d")
            for cycle in cycles_desc:
                url = self.build_s3_grib_url(grid, date_str, cycle, 0)
                if await self.check_grib_exists(url):
                    return date_str, cycle

        return None

    # ------------------------------------------------------------------
    # NDBC buoy data
    # ------------------------------------------------------------------

    async def fetch_ndbc_realtime(self, station_id: str) -> str:
        """Fetch realtime2 standard meteorological data for an NDBC buoy.

        Args:
            station_id: NDBC station ID (e.g., '41025', '46042').

        Returns:
            Raw text content of the realtime2 .txt file.
        """
        url = f"{NDBC_REALTIME_BASE}/{station_id}.txt"
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()
        return response.text

    async def fetch_ndbc_history(
        self,
        station_id: str,
        year: int,
    ) -> str:
        """Fetch historical annual standard meteorological data for an NDBC buoy.

        Args:
            station_id: NDBC station ID.
            year: Year to fetch.

        Returns:
            Raw text content of the historical data file.
        """
        url = f"{NDBC_HISTORY_BASE}"
        params = {
            "filename": f"{station_id}h{year}.txt.gz",
            "dir": "data/historical/stdmet/",
        }
        client = await self._get_client()
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.text

    async def fetch_ndbc_active_stations(self) -> str:
        """Fetch the NDBC active stations XML file.

        Returns:
            Raw XML content.
        """
        client = await self._get_client()
        response = await client.get(NDBC_STATIONS_URL)
        response.raise_for_status()
        return response.text

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
