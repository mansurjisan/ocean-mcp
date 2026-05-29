"""Async HTTP client for OFS data on AWS S3, THREDDS/OPeNDAP, and CO-OPS API."""

from __future__ import annotations

import asyncio
import random
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx

from .models import COOPS_API_BASE, OFS_MODELS, S3_BASE, THREDDS_BASE


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


class OFSAPIError(Exception):
    """Custom exception for OFS API errors."""

    pass


class OFSClient:
    """Async client for OFS data access and CO-OPS observations."""

    def __init__(
        self,
        max_retries: int = 2,
        backoff_factor: float = 0.5,
        cycle_cache_ttl: float = 600.0,
    ) -> None:
        self._client: httpx.AsyncClient | None = None
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor
        # Cache the resolved latest cycle per model for a short TTL. Resolving
        # sweeps up to num_days x cycles (~8) S3 HEADs, and both forecast tools
        # resolve on every call; a cycle publishes every ~6 h, so a 10-min
        # cache is safe and turns repeated lookups within a session into one
        # sweep. cycle_cache_ttl=0 disables it (used by the tests).
        self._cycle_cache: dict[str, tuple[float, tuple[str, str]]] = {}
        self._cycle_cache_ttl = cycle_cache_ttl

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=120.0,
                follow_redirects=True,
                transport=RetryTransport(
                    max_retries=self._max_retries,
                    backoff_factor=self._backoff_factor,
                ),
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
        # Real NOS OFS S3 objects embed the YYYYMMDD date in the filename and
        # use a model-dependent file-type infix (ROMS bay models = "fields",
        # large/2-D models = "2ds"); the previous template hardcoded "fields"
        # and omitted the date, so every S3 URL 404'd.
        # e.g. cbofs/netcdf/2026/05/16/cbofs.t00z.20260516.fields.f001.nc
        file_type = OFS_MODELS.get(model, {}).get("s3_file_type", "fields")
        fname = f"{model}.t{cycle}z.{date}.{file_type}.{ftype}{fhour:03d}.nc"
        return f"{S3_BASE}/{model}/netcdf/{y}/{m}/{d}/{fname}"

    def build_thredds_url(self, model: str) -> str | None:
        """Build the THREDDS OPeNDAP FMRC URL for an OFS model.

        Uses the Forecast Model Run Collection (FMRC) "Best Time Series"
        aggregation which combines the latest nowcast + forecast into a
        continuous time series accessible via OPeNDAP for lazy loading.

        Not all models have FMRC aggregations on THREDDS (NGOFS2, SFBOFS,
        WCOFS do not). Returns None for models without FMRC support.

        Args:
            model: OFS model key (e.g., 'cbofs').

        Returns:
            OPeNDAP URL for the FMRC aggregation, or None if unavailable.
        """
        model_info = OFS_MODELS.get(model, {})
        if not model_info.get("has_fmrc", False):
            return None
        thredds_id = model_info.get("thredds_id", model.upper())
        return (
            f"{THREDDS_BASE}/{thredds_id}/fmrc/"
            f"Aggregated_7_day_{thredds_id}_Fields_Forecast_best.ncd"
        )

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
        """Open a THREDDS OPeNDAP FMRC dataset for lazy remote access.

        Uses netCDF4.Dataset with OPeNDAP — only loads data when variables
        are actually indexed, enabling efficient point extraction.

        Args:
            model: OFS model key (e.g., 'cbofs').

        Returns:
            netCDF4.Dataset opened via OPeNDAP.

        Raises:
            RuntimeError: If OPeNDAP is not available, model has no FMRC,
                or connection fails.
        """
        import netCDF4

        url = self.build_thredds_url(model)
        if url is None:
            raise RuntimeError(
                f"{model.upper()} does not have an FMRC aggregation on THREDDS. "
                "Will use S3 download instead."
            )
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

        now = time.monotonic()
        cached = self._cycle_cache.get(model)
        if cached is not None and now - cached[0] < self._cycle_cache_ttl:
            return cached[1]

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
                    # Cache positive results only — a None could publish moments
                    # later, and caching it would keep failing for the TTL.
                    self._cycle_cache[model] = (now, (date_str, cycle))
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
