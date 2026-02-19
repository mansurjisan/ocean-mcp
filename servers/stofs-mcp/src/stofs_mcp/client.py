"""Async HTTP client for STOFS data on AWS S3 and CO-OPS API."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import httpx

S3_BASE_2D = "https://noaa-gestofs-pds.s3.amazonaws.com"
S3_BASE_3D = "https://noaa-nos-stofs3d-pds.s3.amazonaws.com"
NOMADS_BASE = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/stofs/prod"
OPENDAP_BASE_2D = "https://nomads.ncep.noaa.gov/dods/stofs_2d_glo"
OPENDAP_BASE_3D = "https://nomads.ncep.noaa.gov/dods/stofs_3d_atl"
COOPS_API_BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"


class STOFSAPIError(Exception):
    """Custom exception for STOFS API errors."""
    pass


class STOFSClient:
    """Async client for downloading STOFS data and fetching CO-OPS observations."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=120.0,          # NetCDF downloads can be slow
                follow_redirects=True,
            )
        return self._client

    async def check_file_exists(self, url: str) -> bool:
        """Check if a file exists on S3/NOMADS using HTTP HEAD."""
        client = await self._get_client()
        try:
            response = await client.head(url)
            return response.status_code == 200
        except Exception:
            return False

    async def download_netcdf(self, url: str) -> Path:
        """Download a NetCDF file to a temporary location.

        Args:
            url: Full HTTPS URL to the NetCDF file.

        Returns:
            Path to the temporary file. Caller must delete it.

        Raises:
            httpx.HTTPStatusError: If the file is not found or request fails.
        """
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()

        tmp = tempfile.NamedTemporaryFile(suffix=".nc", delete=False)
        tmp.write(response.content)
        tmp.close()
        return Path(tmp.name)

    async def fetch_coops_observations(
        self,
        station_id: str,
        begin_date: str,
        end_date: str,
        datum: str = "MSL",
    ) -> dict[str, Any]:
        """Fetch CO-OPS observed water levels for comparison.

        Args:
            station_id: CO-OPS station ID (e.g., '8518750').
            begin_date: Start date in YYYYMMDD or 'YYYYMMDD HH:MM' format.
            end_date: End date in YYYYMMDD or 'YYYYMMDD HH:MM' format.
            datum: Vertical datum — 'MSL' for 2D-Global, 'NAVD' for 3D-Atlantic.

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
            "application": "stofs_mcp",
        }
        response = await client.get(COOPS_API_BASE, params=params)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise ValueError(
                f"CO-OPS API error: {data['error'].get('message', 'Unknown error')}"
            )
        return data

    def build_station_url(
        self,
        model: str,
        date: str,
        cycle: str,
        product: str = "cwl",
    ) -> str:
        """Build the AWS S3 URL for a STOFS station NetCDF file.

        Args:
            model: 'two_global' or '3d_atlantic'.
            date: Date in YYYYMMDD format.
            cycle: Cycle hour '00', '06', '12', '18'.
            product: 'cwl', 'htp', or 'swl' (3D only supports 'cwl').

        Returns:
            Full HTTPS URL to the station NetCDF file.
        """
        if model == "2d_global":
            return (
                f"{S3_BASE_2D}/stofs_2d_glo.{date}/"
                f"stofs_2d_glo.t{cycle}z.points.{product}.nc"
            )
        elif model == "3d_atlantic":
            return (
                f"{S3_BASE_3D}/STOFS-3D-Atl/stofs_3d_atl.{date}/"
                f"stofs_3d_atl.t{cycle}z.points.cwl.nc"
            )
        else:
            raise ValueError(
                f"Unknown model '{model}'. Use '2d_global' or '3d_atlantic'."
            )

    def build_opendap_url(
        self,
        model: str,
        date: str,
        cycle: str,
        region: str = "conus.east",
    ) -> str:
        """Build the NOMADS OPeNDAP URL for a STOFS regional-grid dataset.

        NOMADS serves STOFS as per-region regular-grid products. Each region
        has its own URL. The path format is:
          /stofs_2d_glo/{YYYYMMDD}/stofs_2d_glo_{region}_{cycle}z

        Available regions (2D): conus.east, conus.west, alaska, hawaii,
        puertori, guam, northpacific.
        Available regions (3D): conus.east only.

        Args:
            model: '2d_global' or '3d_atlantic'.
            date: Date in YYYYMMDD format.
            cycle: Cycle hour '00', '06', '12', '18'.
            region: NOMADS region name (default 'conus.east').

        Returns:
            OPeNDAP URL string.

        Raises:
            ValueError: If model is not '2d_global' or '3d_atlantic'.
        """
        if model == "2d_global":
            return f"{OPENDAP_BASE_2D}/{date}/stofs_2d_glo_{region}_{cycle}z"
        elif model == "3d_atlantic":
            return f"{OPENDAP_BASE_3D}/{date}/stofs_3d_atl_{region}_{cycle}z"
        else:
            raise ValueError(f"Unknown model '{model}'. Use '2d_global' or '3d_atlantic'.")

    async def check_opendap_available(self, url: str) -> bool:
        """Check if a NOMADS OPeNDAP dataset endpoint is available.

        Fetches the .das (Dataset Attribute Structure). NOMADS returns HTTP 200
        for both available and unavailable datasets, but unavailable ones return
        a body starting with ``Error {``. This method checks the response content.

        Args:
            url: Base OPeNDAP URL (without .das extension).

        Returns:
            True only if the dataset exists and is accessible, False otherwise.
        """
        client = await self._get_client()
        try:
            response = await client.get(f"{url}.das", timeout=15.0)
            if response.status_code != 200:
                return False
            # NOMADS returns 200 with "Error { ... }" body for missing datasets
            return not response.text.strip().startswith("Error {")
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
