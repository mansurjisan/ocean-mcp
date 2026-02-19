# CLAUDE.md — STOFS MCP Server Implementation Guide

## Overview

Build `stofs-mcp` — an MCP server providing AI assistants with access to NOAA's Storm Tide Operational Forecast System (STOFS) operational forecasts and model-vs-observation validation. This server lives in the existing `ocean-mcp` monorepo at `servers/stofs-mcp/`.

**Key constraint**: STOFS does NOT have a JSON REST API like CO-OPS. Data is distributed as NetCDF files on AWS S3 (HTTPS, no auth) and NOMADS. The strategy is to target the **small station-level NetCDF files** (a few MB each) rather than the massive gridded field files (GB+). Download the station file, parse it with `netCDF4`, extract the relevant station(s), and return structured results.

**This server has two audiences**:
1. External users (researchers, forecasters, public) — accessing STOFS forecast guidance
2. Internal modelers — validating STOFS against CO-OPS observations

---

## Monorepo Location

```
ocean-mcp/
├── servers/
│   ├── coops-mcp/          # Existing — tides & water levels
│   ├── erddap-mcp/         # Existing — ERDDAP data access
│   ├── nhc-mcp/            # Existing — scaffold
│   └── stofs-mcp/          # ← BUILD THIS
│       ├── README.md
│       ├── pyproject.toml
│       ├── src/stofs_mcp/
│       │   ├── __init__.py
│       │   ├── __main__.py
│       │   ├── server.py
│       │   ├── client.py        # HTTP client for AWS S3 / NOMADS
│       │   ├── models.py        # Enums, dataclasses
│       │   ├── utils.py         # NetCDF parsing, formatters, error handling
│       │   ├── stations.py      # Station registry (hardcoded station list with CO-OPS IDs)
│       │   └── tools/
│       │       ├── __init__.py
│       │       ├── forecast.py      # Station forecast, point forecast
│       │       ├── discovery.py     # List cycles, system info
│       │       └── validation.py    # Compare with CO-OPS observations
│       ├── tests/
│       │   ├── __init__.py
│       │   ├── test_utils.py
│       │   └── test_live.py
│       └── eval/
│           └── evaluation.xml
```

---

## STOFS System Reference

### Two operational components

**STOFS-2D-Global** (ADCIRC v55+):
- Global unstructured mesh, ~12.8M nodes
- Runs 4x daily: 00, 06, 12, 18 UTC
- 6-hour nowcast + 180-hour (7.5 day) forecast
- ~385 station output points (6-minute resolution)
- Atmospheric forcing: GFS
- Datum: station files use **Local MSL (LMSL)**, SHEF files use **MLLW**

**STOFS-3D-Atlantic** (SCHISM):
- US East Coast + Gulf + Puerto Rico, ~2.9M nodes
- Runs 1x daily at 12 UTC
- 24-hour nowcast + 96-hour (4 day) forecast
- ~108 station output points (6-minute resolution)
- Atmospheric forcing: GFS + HRRR, tidal: FES2014, hydrology: NWM
- Datum: station files use **NAVD88**

### Data access endpoints (all public, no auth)

**AWS S3 (primary — use this)**:
- STOFS-2D-Global: `https://noaa-gestofs-pds.s3.amazonaws.com/stofs_2d_glo.YYYYMMDD/`
- STOFS-3D-Atlantic: `https://noaa-nos-stofs3d-pds.s3.amazonaws.com/stofs_3d_atl.YYYYMMDD/`

**NOMADS (backup, rolling ~2-day window)**:
- STOFS-2D-Global: `https://nomads.ncep.noaa.gov/pub/data/nccf/com/stofs/prod/stofs_2d_glo.YYYYMMDD/`
- STOFS-3D-Atlantic: `https://nomads.ncep.noaa.gov/pub/data/nccf/com/stofs/prod/stofs_3d_atl.YYYYMMDD/`

### Station file naming conventions

**STOFS-2D-Global station NetCDF files** (key files for this MCP server):
- `stofs_2d_glo.tCCz.points.cwl.nc` — Combined Water Level (tide + surge) at stations
- `stofs_2d_glo.tCCz.points.htp.nc` — Harmonic Tidal Prediction only
- `stofs_2d_glo.tCCz.points.swl.nc` — Surge Water Level only (non-tidal residual)

Where CC = cycle hour (00, 06, 12, 18). These files are typically 2-10 MB each.

**STOFS-3D-Atlantic station NetCDF files**:
- `stofs_3d_atl.t12z.points.cwl.nc` — Combined Water Level at stations
- `stofs_3d_atl.t12z.points.cwl.temp.salt.vel.nc` — Water level + temp + salinity + velocity

Only one cycle per day (12z).

### NetCDF variable structure (STOFS-2D-Global station files)

```
Dimensions:
  time: UNLIMITED (variable, typically ~1860 for 186 hours at 6-min)
  station: ~385

Variables:
  time(time)              — seconds since reference time (or datetime64)
  station_name(station)   — station identifier strings (e.g., "8518750" for CO-OPS stations)
  x(station)              — longitude
  y(station)              — latitude
  zeta(time, station)     — water surface elevation (meters, relative to LMSL for 2D, NAVD88 for 3D)
```

The exact variable names may vary slightly between 2D and 3D files. The implementation MUST inspect the NetCDF file to determine actual variable names. Common patterns:
- Water level: `zeta`, `elevation`, `water_level`, `ssh`
- Station name: `station_name`, `station`, `stationid`
- Time: `time`, `ocean_time`
- Coordinates: `x`/`y`, `lon`/`lat`, `longitude`/`latitude`

### Max water level files

- `stofs_2d_glo.tCCz.fields.cwl.maxele.nc` — maximum water level over the full forecast cycle
- This is a single-timestep gridded field (still on the unstructured mesh, but only one time step, so smaller)
- Contains: `zeta_max(node)` — max elevation at each mesh node
- Size: ~100-200 MB (12.8M nodes × 1 float). Too large to fully parse in MCP, but can report metadata.

---

## Tools to Implement (7 tools)

### Tool 1: `stofs_list_cycles`

List available STOFS forecast cycles on AWS S3 for a given date range.

**Inputs**:
- `model`: str — `"2d_global"` or `"3d_atlantic"` (default: `"2d_global"`)
- `date`: str | None — specific date in YYYY-MM-DD format (default: today UTC)
- `num_days`: int — number of past days to check (default: 2, max: 7)

**Implementation**:
- For each date in range, construct the S3 directory URL
- Use HTTP HEAD or GET on the directory listing to check which cycle folders exist
- For STOFS-2D-Global, check cycles 00, 06, 12, 18
- For STOFS-3D-Atlantic, only cycle 12 exists
- Verify existence by checking if the station `points.cwl.nc` file exists (HTTP HEAD request)
- Return list of available cycles with their UTC timestamps and data URLs

**Output**: Markdown table of available cycles with model, date, cycle, status, and download URLs.

**Annotations**: readOnly=True, destructive=False, idempotent=True, openWorld=True

### Tool 2: `stofs_get_station_forecast`

Get STOFS water level forecast time series at a specific station.

**Inputs**:
- `station_id`: str — CO-OPS station ID (e.g., "8518750" for The Battery, NY)
- `model`: str — `"2d_global"` or `"3d_atlantic"` (default: `"2d_global"`)
- `product`: str — `"cwl"` (combined water level), `"htp"` (tidal prediction), or `"swl"` (surge only). Default: `"cwl"`.
- `cycle_date`: str | None — date in YYYY-MM-DD format (default: latest available)
- `cycle_hour`: str | None — cycle hour "00", "06", "12", "18" (default: latest available)
- `response_format`: str — `"markdown"` or `"json"` (default: `"markdown"`)

**Implementation**:
1. Construct the AWS S3 URL for the station NetCDF file:
   - 2D: `https://noaa-gestofs-pds.s3.amazonaws.com/stofs_2d_glo.{date}/stofs_2d_glo.t{CC}z.points.{product}.nc`
   - 3D: `https://noaa-nos-stofs3d-pds.s3.amazonaws.com/stofs_3d_atl.{date}/stofs_3d_atl.t12z.points.cwl.nc`
2. Download the file to a temporary location using httpx (streaming download, ~2-10 MB)
3. Open with `netCDF4.Dataset`
4. Find the station index by matching `station_name` variable against `station_id`
5. Extract the full time series: `zeta[:, station_idx]`
6. Convert time variable to ISO 8601 datetime strings using `netCDF4.num2date`
7. Filter out NaN/fill values
8. Return time series with metadata (model, cycle, datum, station info)

**Output (markdown)**: Header with station info, model, cycle, datum. Table with columns: Time (UTC), Water Level (m), with key statistics (min, max, mean, current). Truncate to first/last N rows if >100 rows, noting total count.

**Output (json)**: Full time series array with metadata.

**Error handling**:
- Station not found in file → list available station IDs, suggest using `stofs_get_system_info`
- File not found on S3 → suggest checking `stofs_list_cycles` for available cycles
- NetCDF read error → provide specific error, suggest trying a different cycle

**Annotations**: readOnly=True, destructive=False, idempotent=True, openWorld=True

### Tool 3: `stofs_get_point_forecast`

Get STOFS forecast at an arbitrary lat/lon point by finding the nearest station.

**Inputs**:
- `latitude`: float — target latitude
- `longitude`: float — target longitude
- `model`: str — `"2d_global"` or `"3d_atlantic"` (default: `"2d_global"`)
- `product`: str — `"cwl"`, `"htp"`, `"swl"` (default: `"cwl"`)
- `cycle_date`: str | None — date (default: latest)
- `cycle_hour`: str | None — cycle hour (default: latest)
- `max_distance_km`: float — maximum distance to nearest station (default: 50.0)
- `response_format`: str — `"markdown"` or `"json"`

**Implementation**:
1. Download the station NetCDF file (same as Tool 2)
2. Read all station coordinates (x, y variables)
3. Compute haversine distance from target lat/lon to all stations
4. Find the nearest station within `max_distance_km`
5. If no station within range, return error with suggestion to try `3d_atlantic` or adjust distance
6. Extract and return time series for that station (same as Tool 2)
7. Include distance to nearest station in the response

**Annotations**: readOnly=True, destructive=False, idempotent=True, openWorld=True

### Tool 4: `stofs_compare_with_observations`

Compare STOFS forecast against CO-OPS observed water levels at a station. This is the validation tool.

**Inputs**:
- `station_id`: str — CO-OPS station ID
- `model`: str — `"2d_global"` or `"3d_atlantic"` (default: `"2d_global"`)
- `cycle_date`: str | None — date (default: latest)
- `cycle_hour`: str | None — cycle hour (default: latest)
- `hours_to_compare`: int — number of hours to compare (default: 24, max: 96). This uses the nowcast + early forecast period where observations exist.
- `response_format`: str — `"markdown"` or `"json"`

**Implementation**:
1. Download the STOFS station file and extract forecast time series (same as Tool 2)
2. Determine the time range for comparison:
   - Use the nowcast period (first 6 hours for 2D, first 24 hours for 3D) plus early forecast hours
   - Clip to `hours_to_compare`
3. Fetch CO-OPS observed water levels for the same time period:
   - Use the CO-OPS Data API: `https://api.tidesandcurrents.noaa.gov/api/prod/datagetter`
   - Parameters: `station={id}&product=water_level&datum=MSL&units=metric&time_zone=gmt&format=json&begin_date={start}&end_date={end}&application=stofs_mcp`
   - NOTE: STOFS-2D uses LMSL, CO-OPS uses station-local MSL — these should be comparable but not identical. Include a datum note in output.
   - STOFS-3D uses NAVD88. CO-OPS can provide `datum=NAVD` for NAVD88 comparison.
4. Align the two time series to matching timestamps (nearest 6-minute interval)
5. Compute statistics:
   - **Bias** (mean error): mean(forecast - observed)
   - **RMSE**: sqrt(mean((forecast - observed)²))
   - **MAE**: mean(|forecast - observed|)
   - **Peak error**: max(|forecast - observed|)
   - **Correlation coefficient** (R)
   - **Number of comparison points**
6. Return side-by-side comparison table (subsampled if too many rows) and summary statistics

**Output (markdown)**:
```
## STOFS vs Observations — Station 8518750 (The Battery, NY)
**Model**: STOFS-2D-Global | **Cycle**: 2026-02-18 00z | **Period**: 24 hours
**STOFS Datum**: LMSL | **Obs Datum**: MSL | ⚠️ Small datum offsets may exist

### Summary Statistics
| Metric | Value |
| --- | --- |
| Bias (mean error) | +0.03 m |
| RMSE | 0.08 m |
| MAE | 0.06 m |
| Peak Error | 0.15 m |
| Correlation (R) | 0.97 |
| Comparison Points | 240 |

### Time Series Comparison (hourly sample)
| Time (UTC) | STOFS (m) | Observed (m) | Error (m) |
| --- | --- | --- | --- |
| 2026-02-18 00:00 | 0.45 | 0.42 | +0.03 |
...
```

**Annotations**: readOnly=True, destructive=False, idempotent=True, openWorld=True

### Tool 5: `stofs_get_max_water_level`

Get the maximum water level from a STOFS forecast cycle. Reports metadata and station-level max values (from the station file), NOT the full gridded maxele field.

**Inputs**:
- `model`: str — `"2d_global"` or `"3d_atlantic"` (default: `"2d_global"`)
- `cycle_date`: str | None
- `cycle_hour`: str | None
- `top_n`: int — return top N stations by max water level (default: 20)
- `region`: str | None — optional filter: "east_coast", "gulf", "west_coast", "alaska", "hawaii", "puerto_rico"
- `response_format`: str — `"markdown"` or `"json"`

**Implementation**:
1. Download the station NetCDF file
2. Compute max water level across all timesteps for each station: `max(zeta[:, i])` for each station i
3. Optionally filter by region using station coordinates (rough bounding boxes)
4. Sort by max water level descending
5. Return top N stations with their max values, coordinates, and times of maximum

**Annotations**: readOnly=True, destructive=False, idempotent=True, openWorld=True

### Tool 6: `stofs_get_system_info`

Get STOFS system metadata — model specifications, station lists, datum references, cycle schedule.

**Inputs**:
- `model`: str | None — `"2d_global"`, `"3d_atlantic"`, or None for both (default: None)
- `include_stations`: bool — whether to include the full station list (default: False)

**Implementation**:
- Return hardcoded system information (model specs, datums, cycle schedule)
- If `include_stations=True`, download the latest station file and extract station names, coordinates
- Or use a hardcoded station registry (see stations.py below)

**Output**: Model description, mesh size, forcing, cycle schedule, datum reference, station count. If stations requested, include table of station IDs, names, coordinates.

**Annotations**: readOnly=True, destructive=False, idempotent=True, openWorld=False

### Tool 7: `stofs_list_stations`

List STOFS output stations, optionally filtered by region or proximity to a point.

**Inputs**:
- `model`: str — `"2d_global"` or `"3d_atlantic"` (default: `"2d_global"`)
- `near_lat`: float | None — filter to stations near this latitude
- `near_lon`: float | None — filter to stations near this longitude
- `radius_km`: float — search radius (default: 100)
- `state`: str | None — filter by US state abbreviation (e.g., "NY", "FL")
- `limit`: int — max stations to return (default: 20)

**Implementation**:
1. Download the latest station file (or use cached/hardcoded station registry)
2. Extract station IDs, coordinates, and names
3. Apply filters (region bounding box, haversine distance, state lookup)
4. Return filtered station list

**Annotations**: readOnly=True, destructive=False, idempotent=True, openWorld=True

---

## Client Implementation (client.py)

```python
"""Async HTTP client for STOFS data on AWS S3 and NOMADS."""

import tempfile
from pathlib import Path
import httpx

S3_BASE_2D = "https://noaa-gestofs-pds.s3.amazonaws.com"
S3_BASE_3D = "https://noaa-nos-stofs3d-pds.s3.amazonaws.com"
NOMADS_BASE = "https://nomads.ncep.noaa.gov/pub/data/nccf/com/stofs/prod"
COOPS_API_BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"


class STOFSClient:
    """Async client for downloading STOFS data and CO-OPS observations."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=120.0,  # NetCDF downloads can be slow
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
        """Download a NetCDF file to a temporary location. Returns the file path."""
        client = await self._get_client()
        response = await client.get(url)
        response.raise_for_status()

        # Write to temp file
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
    ) -> dict:
        """Fetch CO-OPS observed water levels for comparison.

        Args:
            station_id: CO-OPS station ID
            begin_date: Start date YYYYMMDD or YYYYMMDD HH:MM
            end_date: End date YYYYMMDD or YYYYMMDD HH:MM
            datum: Vertical datum (MSL, NAVD, MLLW)
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
            raise ValueError(f"CO-OPS API error: {data['error'].get('message', 'Unknown')}")
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
            model: "2d_global" or "3d_atlantic"
            date: YYYYMMDD format
            cycle: "00", "06", "12", "18"
            product: "cwl", "htp", "swl"
        """
        if model == "2d_global":
            return f"{S3_BASE_2D}/stofs_2d_glo.{date}/stofs_2d_glo.t{cycle}z.points.{product}.nc"
        elif model == "3d_atlantic":
            return f"{S3_BASE_3D}/stofs_3d_atl.{date}/stofs_3d_atl.t{cycle}z.points.cwl.nc"
        else:
            raise ValueError(f"Unknown model: {model}. Use '2d_global' or '3d_atlantic'.")

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
```

**Key design decisions**:
- `timeout=120.0` because NetCDF downloads from S3 can take 10-30 seconds
- Downloads to temp file because netCDF4 needs a file path (no streaming parse)
- CO-OPS API integration is built directly into this client since stofs-mcp uses it for validation
- Always clean up temp files after parsing (use try/finally in tools)

---

## Utils Implementation (utils.py)

Must include:

### `parse_station_netcdf(filepath, station_id=None)`
Open a STOFS station NetCDF file with `netCDF4.Dataset`, extract:
- Time array → convert to ISO 8601 strings via `netCDF4.num2date`
- Station names/IDs → decode bytes to strings if needed
- Water level data → `zeta[:, station_idx]` or equivalent
- Station coordinates → lat/lon arrays
- Handle fill values / NaN masking

If `station_id` is given, return only that station's data. Otherwise return metadata about all stations.

### `find_nearest_station(target_lat, target_lon, station_lats, station_lons, station_names)`
Compute haversine distance to all stations, return nearest. Reuse the haversine formula pattern from CO-OPS utils.

### `compute_validation_stats(forecast, observed)`
Given two aligned numpy arrays, compute bias, RMSE, MAE, peak error, correlation coefficient. Return as dict.

### `align_timeseries(forecast_times, forecast_values, observed_times, observed_values)`
Align two irregular time series to common timestamps (nearest 6-minute match). Return aligned arrays. Use `numpy` for efficiency.

### `format_timeseries_table(times, values, title, metadata_lines, ...)`
Markdown table formatter for time series data. Subsample if >100 rows (show every Nth row). Include min/max/mean summary.

### `format_station_table(stations, title, ...)`
Markdown table formatter for station lists.

### `handle_stofs_error(e, model, url)`
Error handler with actionable suggestions specific to STOFS. Patterns:
- 404 → "Cycle not yet available. Use stofs_list_cycles to check available data."
- 403 → "AWS S3 access denied. Data may have been archived. Try a more recent date."
- Timeout → "Download timed out. The file may be large. Try again or use a different cycle."
- NetCDF error → "Error reading STOFS NetCDF file. The file may be corrupted or format may have changed."

### `resolve_latest_cycle(client, model)`
Find the latest available cycle by checking today and yesterday, most recent cycle first. For 2D, check 18z → 12z → 06z → 00z of today, then same for yesterday. For 3D, check 12z of today then yesterday. Use `check_file_exists()`.

### `cleanup_temp_file(filepath)`
Remove a temporary NetCDF file. Called in finally blocks.

---

## Station Registry (stations.py)

Hardcode a basic station registry for quick lookups without downloading NetCDF files. This is used by `stofs_list_stations` and `stofs_get_system_info` when a NetCDF download isn't desired.

Include at least the ~40 most important CO-OPS stations that are in both STOFS-2D and STOFS-3D:

```python
STOFS_STATIONS = [
    {"id": "8518750", "name": "The Battery", "state": "NY", "lat": 40.7006, "lon": -74.0142},
    {"id": "8461490", "name": "New London", "state": "CT", "lat": 41.3614, "lon": -72.0900},
    {"id": "8443970", "name": "Boston", "state": "MA", "lat": 42.3539, "lon": -71.0503},
    {"id": "8658120", "name": "Wilmington", "state": "NC", "lat": 34.2275, "lon": -77.9536},
    {"id": "8665530", "name": "Charleston", "state": "SC", "lat": 32.7817, "lon": -79.9250},
    {"id": "8670870", "name": "Fort Pulaski", "state": "GA", "lat": 32.0367, "lon": -80.9017},
    {"id": "8720218", "name": "Mayport", "state": "FL", "lat": 30.3967, "lon": -81.4300},
    {"id": "8723214", "name": "Virginia Key", "state": "FL", "lat": 25.7317, "lon": -80.1617},
    {"id": "8724580", "name": "Key West", "state": "FL", "lat": 24.5508, "lon": -81.8075},
    {"id": "8726520", "name": "St. Petersburg", "state": "FL", "lat": 27.7606, "lon": -82.6269},
    {"id": "8771341", "name": "Galveston Bay Entrance", "state": "TX", "lat": 29.3572, "lon": -94.7247},
    {"id": "8779770", "name": "Port Isabel", "state": "TX", "lat": 26.0617, "lon": -97.2150},
    {"id": "9414290", "name": "San Francisco", "state": "CA", "lat": 37.8063, "lon": -122.4659},
    {"id": "9447130", "name": "Seattle", "state": "WA", "lat": 47.6026, "lon": -122.3393},
    {"id": "9457292", "name": "Cordova", "state": "AK", "lat": 60.5583, "lon": -145.7533},
    {"id": "1611400", "name": "Nawiliwili", "state": "HI", "lat": 21.9544, "lon": -159.3561},
    {"id": "1631428", "name": "Pago Pago", "state": "AS", "lat": -14.2767, "lon": -170.6900},
    {"id": "9751381", "name": "Lameshur Bay", "state": "VI", "lat": 18.3183, "lon": -64.7233},
    {"id": "9755371", "name": "San Juan", "state": "PR", "lat": 18.4597, "lon": -66.1164},
    # ... Add ~20 more key stations. Get the full list from a downloaded station file if needed.
]
```

Also include bounding boxes for region filtering:
```python
REGIONS = {
    "east_coast": {"lat_min": 24.0, "lat_max": 47.0, "lon_min": -82.0, "lon_max": -65.0},
    "gulf": {"lat_min": 24.0, "lat_max": 31.0, "lon_min": -98.0, "lon_max": -82.0},
    "west_coast": {"lat_min": 32.0, "lat_max": 49.0, "lon_min": -125.0, "lon_max": -117.0},
    "alaska": {"lat_min": 51.0, "lat_max": 72.0, "lon_min": -180.0, "lon_max": -130.0},
    "hawaii": {"lat_min": 18.0, "lat_max": 23.0, "lon_min": -161.0, "lon_max": -154.0},
    "puerto_rico": {"lat_min": 17.0, "lat_max": 19.0, "lon_min": -68.0, "lon_max": -64.0},
}
```

---

## Models (models.py)

```python
from enum import Enum

class STOFSModel(str, Enum):
    GLOBAL_2D = "2d_global"
    ATLANTIC_3D = "3d_atlantic"

class STOFSProduct(str, Enum):
    CWL = "cwl"   # Combined Water Level (tide + surge)
    HTP = "htp"   # Harmonic Tidal Prediction
    SWL = "swl"   # Surge Water Level (non-tidal residual)

class Region(str, Enum):
    EAST_COAST = "east_coast"
    GULF = "gulf"
    WEST_COAST = "west_coast"
    ALASKA = "alaska"
    HAWAII = "hawaii"
    PUERTO_RICO = "puerto_rico"
```

---

## pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "stofs-mcp"
version = "0.1.0"
description = "MCP server for NOAA STOFS storm surge forecast access and validation against CO-OPS observations"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
dependencies = [
    "mcp[cli]>=1.0.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
    "netCDF4>=1.7.0",
    "numpy>=1.26.0",
]

[project.scripts]
stofs-mcp = "stofs_mcp.server:main"

[tool.hatch.build.targets.wheel]
packages = ["src/stofs_mcp"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
]
```

**Key difference from other servers**: `netCDF4` and `numpy` are required dependencies. These are well-established scientific Python packages available on PyPI.

---

## Server Pattern (server.py)

Follow the exact same pattern as coops-mcp and erddap-mcp:

```python
"""FastMCP server entry point for STOFS MCP."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from .client import STOFSClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared STOFS client lifecycle."""
    client = STOFSClient()
    try:
        yield {"stofs_client": client}
    finally:
        await client.close()


mcp = FastMCP("stofs_mcp", lifespan=app_lifespan)

# Import tool modules to register them
from .tools import discovery, forecast, validation  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
```

---

## Tests

### Unit tests (test_utils.py)
- `test_haversine_distance` — known distance between two points
- `test_compute_validation_stats` — bias, RMSE, MAE with known arrays
- `test_align_timeseries` — alignment of two time series with different timestamps
- `test_build_station_url_2d` — correct URL construction for 2D model
- `test_build_station_url_3d` — correct URL construction for 3D model
- `test_resolve_region_filter` — bounding box filtering

### Live integration tests (test_live.py)
1. `test_check_latest_2d_cycle_exists` — HEAD request to verify today's or yesterday's 2D station file exists on S3
2. `test_download_and_parse_station_file` — download a 2D station file, open with netCDF4, verify dimensions and variables exist
3. `test_extract_single_station` — download file, extract The Battery (8518750), verify non-empty time series
4. `test_coops_observation_fetch` — fetch 24 hours of CO-OPS water level data, verify JSON structure
5. `test_3d_atlantic_station_file` — download 3D-Atlantic station file, verify structure

---

## Evaluation (eval/evaluation.xml)

10 questions testing multi-tool workflows:

1. "What is the latest available STOFS-2D-Global forecast cycle?"
   - Tools: `stofs_list_cycles`

2. "Get the STOFS water level forecast for The Battery, NY (station 8518750) for the most recent cycle"
   - Tools: `stofs_get_station_forecast`

3. "What are the top 10 stations with highest predicted water levels in the latest STOFS-2D-Global forecast?"
   - Tools: `stofs_get_max_water_level`

4. "Compare STOFS-2D-Global forecast against CO-OPS observations at Boston (8443970) for the past 24 hours"
   - Tools: `stofs_compare_with_observations`

5. "Find STOFS output stations within 50 km of Miami Beach (lat 25.79, lon -80.13)"
   - Tools: `stofs_list_stations` or `stofs_get_point_forecast`

6. "What is the surge-only (non-tidal) forecast at Charleston, SC (8665530)?"
   - Tools: `stofs_get_station_forecast` with product="swl"

7. "How does STOFS-3D-Atlantic forecast compare to STOFS-2D-Global at The Battery for the latest cycle?"
   - Tools: `stofs_get_station_forecast` (called twice, once per model)

8. "What are the differences between STOFS-2D-Global and STOFS-3D-Atlantic in terms of coverage and resolution?"
   - Tools: `stofs_get_system_info`

9. "Get the STOFS forecast at lat 29.95, lon -90.07 (near New Orleans) and compare it with observations"
   - Tools: `stofs_get_point_forecast`, `stofs_compare_with_observations`

10. "List all STOFS stations in Texas and show the latest forecast for the station with the highest surge"
    - Tools: `stofs_list_stations`, `stofs_get_station_forecast`

---

## README.md for stofs-mcp

Include:
- Title: "STOFS MCP Server"
- Description: Access NOAA's Storm Tide Operational Forecast System (STOFS) forecasts and validate against CO-OPS observations
- Status: "Ready"
- Features list: station forecasts, point queries, observation validation, max water levels, system info
- Quick start (clone, uv sync, configure MCP client)
- Tool reference table
- Example queries
- Data sources: AWS S3 (noaa-gestofs-pds, noaa-nos-stofs3d-pds), NOMADS, CO-OPS API
- Note about vertical datums (LMSL, NAVD88, MLLW differences)
- License: MIT

---

## Important Implementation Notes

1. **Always clean up temp NetCDF files.** Every tool that downloads a NetCDF file must use try/finally to delete the temp file. Otherwise the server will leak disk space.

2. **netCDF4 station name encoding.** Station names in ADCIRC NetCDF files may be stored as byte arrays or character arrays. Always handle decoding: `station_name.tobytes().decode().strip()` or `"".join(s.decode() for s in station_name).strip()`.

3. **Time variable handling.** STOFS time variables use `seconds since YYYY-MM-DD HH:MM:SS`. Use `netCDF4.num2date(times, units=time_var.units, calendar=time_var.calendar)` to convert. Some files may lack a `calendar` attribute — default to `"standard"`.

4. **Fill values.** STOFS NetCDF files use fill values (typically -99999 or 1e37) for dry nodes or missing data. Always check `numpy.ma.is_masked()` or compare against `_FillValue` attribute. Filter these out before computing statistics or returning to users.

5. **S3 file availability timing.** STOFS-2D-Global products arrive ~2-3.5 hours after cycle time. STOFS-3D-Atlantic products arrive ~4-5 hours after 12z. If the latest cycle isn't available yet, fall back to the previous cycle automatically.

6. **Datum differences matter.** When comparing STOFS with CO-OPS:
   - STOFS-2D station files: LMSL (Local Mean Sea Level)
   - STOFS-3D station files: NAVD88
   - CO-OPS API: request `datum=MSL` for 2D comparison, `datum=NAVD` for 3D comparison
   - Always note the datum in output. Small systematic offsets (1-5 cm) are expected.

7. **Don't try to parse the full gridded field files.** Files like `stofs_2d_glo.t00z.fields.cwl.nc` contain 12.8M nodes per timestep × many timesteps = gigabytes. Only use the `points` (station) files.

8. **3D-Atlantic has fewer stations and fewer products.** Only ~108 stations vs ~385 for 2D. Only CWL product (no separate HTP/SWL files). Only 12z cycle. Handle gracefully when users request unavailable combinations.

9. **Follow existing monorepo patterns exactly.** Same server.py lifespan pattern, same `_get_client(ctx)` helper in tools, same annotation style, same markdown/json dual output.

---

## Post-Build Tasks

After Claude Code builds the server:

1. Update the root `ocean-mcp/README.md` server table to show stofs-mcp as "Ready"
2. Update `ocean-mcp/docs/architecture.md` to mention stofs-mcp and its unique NetCDF-based access pattern
3. Add stofs-mcp to the MCP client config example in the root README
4. Run `cd servers/stofs-mcp && uv sync` to verify dependencies install
5. Run `uv run pytest tests/test_utils.py -v` for unit tests
6. Run `uv run pytest tests/test_live.py -v -s` for live integration tests (requires internet)
7. Test the server: `uv run python -m stofs_mcp.server`
