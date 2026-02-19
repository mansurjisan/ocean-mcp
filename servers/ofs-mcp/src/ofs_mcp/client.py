"""Async HTTP client for OFS data on AWS S3, THREDDS/OPeNDAP, and CO-OPS API."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import httpx

from .models import COOPS_API_BASE, OFS_MODELS, S3_BASE, THREDDS_BASE


class OFSAPIError(Exception):
    """Custom exception for OFS API errors."""
    pass


class OFSClient:
    """Async client for OFS data access and CO-OPS observations."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=120.0,
                follow_redirects=True,
            )
        return self._client

    async def check_file_exists(self, url: str) -> bool:
        """Check if a file exists using HTTP HEAD."""
        client = await self._get_client()
        try:
            response = await client.head(url)
            return response.status_code == 200
        except Exception:
            return False

    def build_s3_url(
        self,
        model: str,
        date: str,
        cycle: str,
        ftype: str = "f",
        fhour: int = 1,
    ) -> str:
        """Build the S3 URL for an OFS fields NetCDF file.

        Args:
            model: OFS model key (e.g., 'cbofs').
            date: Date in YYYYMMDD format.
            cycle: Cycle hour (e.g., '00', '06', '12', '18').
            ftype: 'f' for forecast, 'n' for nowcast.
            fhour: Forecast/nowcast hour number (1-indexed).

        Returns:
            Full HTTPS URL to the NetCDF file on S3.
        """
        y, m, d = date[:4], date[4:6], date[6:8]
        fname = f"{model}.t{cycle}z.fields.{ftype}{fhour:03d}.nc"
        return f"{S3_BASE}/{model}/netcdf/{y}/{m}/{d}/{fname}"

    def build_thredds_url(self, model: str) -> str:
        """Build the THREDDS OPeNDAP URL for the BEST aggregation of an OFS model.

        The BEST aggregation combines the most recent nowcast and forecast data
        into a continuous time series accessible via OPeNDAP for lazy loading.

        Args:
            model: OFS model key (e.g., 'cbofs').

        Returns:
            OPeNDAP URL for the BEST aggregation dataset.
        """
        model_info = OFS_MODELS.get(model, {})
        thredds_id = model_info.get("thredds_id", model.upper())
        return f"{THREDDS_BASE}/{thredds_id}/{thredds_id}_BEST.nc"

    async def download_netcdf(self, url: str) -> Path:
        """Download a NetCDF file to a temporary location.

        Args:
            url: Full HTTPS URL to the NetCDF file.

        Returns:
            Path to the temporary file. Caller is responsible for deletion.

        Raises:
            httpx.HTTPStatusError: If the request fails.
        """
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()

        tmp = tempfile.NamedTemporaryFile(suffix=".nc", delete=False)
        tmp.write(response.content)
        tmp.close()
        return Path(tmp.name)

    def open_opendap(self, model: str):
        """Open a THREDDS OPeNDAP dataset for lazy remote access.

        Uses netCDF4.Dataset with OPeNDAP — only loads data when variables
        are actually indexed, enabling efficient point extraction.

        Args:
            model: OFS model key (e.g., 'cbofs').

        Returns:
            netCDF4.Dataset opened via OPeNDAP.

        Raises:
            RuntimeError: If OPeNDAP is not available or connection fails.
        """
        import netCDF4

        url = self.build_thredds_url(model)
        try:
            nc = netCDF4.Dataset(url)
            return nc
        except Exception as e:
            raise RuntimeError(
                f"Failed to open OPeNDAP dataset for {model.upper()} at {url}. "
                f"Error: {e}\n\n"
                "Possible causes:\n"
                "- THREDDS server temporarily unavailable\n"
                "- netCDF4 library not compiled with DAP support\n"
                "- Network connectivity issue\n\n"
                "Try using a different model or check cycle availability with ofs_list_cycles."
            ) from e

    async def resolve_latest_cycle(
        self,
        model: str,
        num_days: int = 2,
    ) -> tuple[str, str] | None:
        """Find the latest available OFS cycle on AWS S3.

        Args:
            model: OFS model key (e.g., 'cbofs').
            num_days: Number of past days to check (default: 2).

        Returns:
            (date_str, cycle_str) tuple (YYYYMMDD, CC), or None if not found.
        """
        from datetime import datetime, timedelta, timezone

        model_info = OFS_MODELS.get(model, {})
        cycles = model_info.get("cycles", ["00", "06", "12", "18"])
        # Check newest first
        cycles_desc = sorted(cycles, reverse=True)

        today = datetime.now(timezone.utc)
        for day_offset in range(num_days):
            date = today - timedelta(days=day_offset)
            date_str = date.strftime("%Y%m%d")
            for cycle in cycles_desc:
                url = self.build_s3_url(model, date_str, cycle, "f", 1)
                if await self.check_file_exists(url):
                    return date_str, cycle

        return None

    async def fetch_coops_observations(
        self,
        station_id: str,
        begin_date: str,
        end_date: str,
        datum: str = "NAVD",
    ) -> dict[str, Any]:
        """Fetch CO-OPS observed water levels.

        Args:
            station_id: CO-OPS station ID (e.g., '8571892').
            begin_date: Start date (YYYYMMDD or 'YYYYMMDD HH:MM').
            end_date: End date (YYYYMMDD or 'YYYYMMDD HH:MM').
            datum: Vertical datum — 'NAVD' for NAVD88, 'MSL', 'MLLW', etc.

        Returns:
            CO-OPS API JSON response with 'data' list.

        Raises:
            ValueError: If the CO-OPS API returns an error.
        """
        client = await self._get_client()
        params = {
            "station": station_id,
            "product": "water_level",
            "datum": datum,
            "units": "metric",
            "time_zone": "gmt",
            "format": "json",
            "begin_date": begin_date,
            "end_date": end_date,
            "application": "ofs_mcp",
        }
        response = await client.get(COOPS_API_BASE, params=params)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise ValueError(
                f"CO-OPS API error: {data['error'].get('message', 'Unknown error')}"
            )
        return data

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
