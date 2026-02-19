"""Parsers, formatters, and helper utilities for STOFS data."""

from __future__ import annotations

import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# NetCDF parsing
# ---------------------------------------------------------------------------

def _detect_variable(nc, candidates: list[str]):
    """Return the first variable name found in the NetCDF dataset."""
    for name in candidates:
        if name in nc.variables:
            return name
    return None


def _decode_station_names(var) -> list[str]:
    """Decode station names from a NetCDF character or byte array variable."""
    import numpy as np

    data = var[:]
    if hasattr(data, "data"):
        data = data.data

    names = []
    # 2D char array: shape (n_stations, str_len)
    if data.ndim == 2:
        for row in data:
            chars = []
            for c in row:
                if isinstance(c, (bytes, np.bytes_)):
                    ch = c.decode("utf-8", errors="replace")
                else:
                    ch = str(c) if c else ""
                chars.append(ch)
            name = "".join(chars).strip("\x00").strip()
            names.append(name)
    # 1D array of bytes or strings
    elif data.ndim == 1:
        for item in data:
            if isinstance(item, (bytes, np.bytes_)):
                name = item.decode("utf-8", errors="replace").strip("\x00").strip()
            else:
                name = str(item).strip("\x00").strip()
            names.append(name)
    return names


def parse_station_netcdf(
    filepath: Path | str,
    station_id: str | None = None,
) -> dict[str, Any]:
    """Open a STOFS station NetCDF file and extract water level time series.

    Args:
        filepath: Path to the downloaded NetCDF file.
        station_id: CO-OPS station ID to extract. If None, returns metadata
                    about all stations without time series data.

    Returns:
        Dict with keys:
            - 'station_names': list of all station ID strings
            - 'lats': list of latitudes
            - 'lons': list of longitudes
            - 'n_stations': total station count
            - 'n_times': total time steps
            - 'datum': datum attribute if available
            If station_id provided, also:
            - 'station_id': the matched station ID
            - 'station_idx': index in the array
            - 'times': list of ISO 8601 datetime strings
            - 'values': list of water level values (m), NaN filtered
            - 'lat': station latitude
            - 'lon': station longitude
            - 'model_start': first time string
            - 'model_end': last time string

    Raises:
        ValueError: If station_id is not found in the file.
        RuntimeError: If required variables are missing.
    """
    import netCDF4
    import numpy as np

    nc = netCDF4.Dataset(str(filepath), "r")
    try:
        # --- Detect variable names ---
        time_var_name = _detect_variable(nc, ["time", "ocean_time"])
        zeta_var_name = _detect_variable(nc, ["zeta", "elevation", "water_level", "ssh"])
        sname_var_name = _detect_variable(nc, ["station_name", "station", "stationid"])
        lat_var_name = _detect_variable(nc, ["y", "lat", "latitude"])
        lon_var_name = _detect_variable(nc, ["x", "lon", "longitude"])

        if not time_var_name:
            raise RuntimeError("Could not find time variable in NetCDF file.")
        if not zeta_var_name:
            raise RuntimeError("Could not find water level variable in NetCDF file.")

        # --- Station names ---
        station_names: list[str] = []
        if sname_var_name:
            station_names = _decode_station_names(nc.variables[sname_var_name])

        # --- Coordinates ---
        lats: list[float] = []
        lons: list[float] = []
        if lat_var_name:
            lats = list(float(v) for v in np.array(nc.variables[lat_var_name][:]).ravel())
        if lon_var_name:
            lons = list(float(v) for v in np.array(nc.variables[lon_var_name][:]).ravel())

        n_stations = len(station_names) or (len(lats) if lats else 0)
        n_times = len(nc.variables[time_var_name])

        # --- Datum attribute ---
        datum = getattr(nc, "datum", getattr(nc, "vertical_datum", ""))

        result: dict[str, Any] = {
            "station_names": station_names,
            "lats": lats,
            "lons": lons,
            "n_stations": n_stations,
            "n_times": n_times,
            "datum": datum,
        }

        if station_id is None:
            return result

        # --- Find station index ---
        station_idx = None
        for i, name in enumerate(station_names):
            if station_id in name or name.strip() == station_id:
                station_idx = i
                break

        if station_idx is None:
            raise ValueError(
                f"Station '{station_id}' not found in this STOFS file. "
                f"Available station IDs (first 20): "
                f"{', '.join(station_names[:20])}"
            )

        # --- Time array ---
        time_var = nc.variables[time_var_name]
        units = getattr(time_var, "units", "seconds since 1970-01-01 00:00:00")
        calendar = getattr(time_var, "calendar", "standard")
        raw_times = time_var[:]
        if hasattr(raw_times, "data"):
            raw_times = raw_times.data

        datetimes = netCDF4.num2date(raw_times, units=units, calendar=calendar)
        time_strings = [dt.strftime("%Y-%m-%d %H:%M") for dt in datetimes]

        # --- Water level time series ---
        zeta = nc.variables[zeta_var_name]
        fill_value = getattr(zeta, "_FillValue", None)

        # zeta shape: (time, station)
        values_raw = np.array(zeta[:, station_idx])

        # Mask fill values
        if fill_value is not None:
            mask = np.abs(values_raw) > 1e10
            mask |= values_raw == fill_value
        else:
            mask = np.abs(values_raw) > 1e10

        # Build filtered lists
        times_out = []
        values_out = []
        for t_str, v, m in zip(time_strings, values_raw.tolist(), mask.tolist()):
            if not m:
                times_out.append(t_str)
                values_out.append(round(float(v), 4))

        station_lat = lats[station_idx] if lats else None
        station_lon = lons[station_idx] if lons else None

        result.update({
            "station_id": station_id,
            "station_idx": station_idx,
            "times": times_out,
            "values": values_out,
            "lat": station_lat,
            "lon": station_lon,
            "model_start": time_strings[0] if time_strings else "",
            "model_end": time_strings[-1] if time_strings else "",
        })
        return result

    finally:
        nc.close()


# ---------------------------------------------------------------------------
# Nearest station finder
# ---------------------------------------------------------------------------

def find_nearest_station(
    target_lat: float,
    target_lon: float,
    station_lats: list[float],
    station_lons: list[float],
    station_names: list[str],
    max_distance_km: float = 50.0,
) -> tuple[int, str, float] | None:
    """Find the nearest station within max_distance_km.

    Returns:
        (index, station_name, distance_km) or None if none within range.
    """
    best_idx = None
    best_dist = float("inf")

    for i, (lat, lon) in enumerate(zip(station_lats, station_lons)):
        dist = _haversine(target_lat, target_lon, lat, lon)
        if dist < best_dist:
            best_dist = dist
            best_idx = i

    if best_idx is None or best_dist > max_distance_km:
        return None

    return best_idx, station_names[best_idx], best_dist


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Validation statistics
# ---------------------------------------------------------------------------

def compute_validation_stats(
    forecast: list[float],
    observed: list[float],
) -> dict[str, float]:
    """Compute bias, RMSE, MAE, peak error, and correlation for aligned arrays.

    Args:
        forecast: List of STOFS forecast values (m).
        observed: List of CO-OPS observed values (m), same length as forecast.

    Returns:
        Dict with keys: bias, rmse, mae, peak_error, correlation, n.
    """
    import numpy as np

    f = np.array(forecast, dtype=float)
    o = np.array(observed, dtype=float)

    if len(f) == 0 or len(f) != len(o):
        return {"bias": None, "rmse": None, "mae": None, "peak_error": None, "correlation": None, "n": 0}

    diff = f - o
    bias = float(np.mean(diff))
    rmse = float(np.sqrt(np.mean(diff ** 2)))
    mae = float(np.mean(np.abs(diff)))
    peak_error = float(np.max(np.abs(diff)))

    # Correlation
    if np.std(f) > 0 and np.std(o) > 0:
        correlation = float(np.corrcoef(f, o)[0, 1])
    else:
        correlation = float("nan")

    return {
        "bias": round(bias, 4),
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        "peak_error": round(peak_error, 4),
        "correlation": round(correlation, 4),
        "n": int(len(f)),
    }


# ---------------------------------------------------------------------------
# Time series alignment
# ---------------------------------------------------------------------------

def align_timeseries(
    forecast_times: list[str],
    forecast_values: list[float],
    observed_times: list[str],
    observed_values: list[float],
    tolerance_minutes: int = 3,
) -> tuple[list[str], list[float], list[float]]:
    """Align two time series to common timestamps.

    Matches forecast times to the nearest observed timestamp within
    tolerance_minutes. Returns only matched pairs.

    Args:
        forecast_times: List of 'YYYY-MM-DD HH:MM' strings.
        forecast_values: Corresponding forecast values.
        observed_times: List of 'YYYY-MM-DD HH:MM' strings.
        observed_values: Corresponding observed values.
        tolerance_minutes: Max time difference for a match (default 3).

    Returns:
        (common_times, aligned_forecast, aligned_observed) lists.
    """
    from datetime import timedelta

    def parse_dt(s: str) -> datetime:
        for fmt in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%m/%d/%Y %H:%M"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse datetime: {s!r}")

    tol = tolerance_minutes * 60  # seconds

    obs_dts = [parse_dt(t) for t in observed_times]
    obs_timestamps = [dt.timestamp() for dt in obs_dts]

    common_times = []
    aligned_forecast = []
    aligned_observed = []

    for f_t_str, f_v in zip(forecast_times, forecast_values):
        try:
            f_dt = parse_dt(f_t_str)
        except ValueError:
            continue
        f_ts = f_dt.timestamp()

        # Find nearest observed
        best_i = None
        best_diff = float("inf")
        for i, o_ts in enumerate(obs_timestamps):
            diff = abs(f_ts - o_ts)
            if diff < best_diff:
                best_diff = diff
                best_i = i

        if best_i is not None and best_diff <= tol:
            common_times.append(f_t_str)
            aligned_forecast.append(f_v)
            aligned_observed.append(observed_values[best_i])

    return common_times, aligned_forecast, aligned_observed


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_timeseries_table(
    times: list[str],
    values: list[float],
    title: str = "",
    metadata_lines: list[str] | None = None,
    max_rows: int = 100,
    source: str = "NOAA STOFS",
) -> str:
    """Format a water level time series as a markdown table.

    Subsamples to max_rows if longer. Includes min/max/mean summary.
    """
    lines: list[str] = []

    if title:
        lines.append(f"## {title}")

    if metadata_lines:
        for m in metadata_lines:
            lines.append(f"**{m}**")
        lines.append("")

    total = len(times)
    if total == 0:
        lines.append("*No data available.*")
        return "\n".join(lines)

    # Compute summary
    import numpy as np
    vals = [v for v in values if v is not None]
    if vals:
        v_min = min(vals)
        v_max = max(vals)
        v_mean = float(np.mean(vals))
        lines.append(
            f"**Min**: {v_min:.3f} m | **Max**: {v_max:.3f} m | "
            f"**Mean**: {v_mean:.3f} m | **Total points**: {total}"
        )
        lines.append("")

    # Subsample
    if total > max_rows:
        step = max(1, total // max_rows)
        indices = list(range(0, total, step))
        times_show = [times[i] for i in indices]
        values_show = [values[i] for i in indices]
        lines.append(f"*Showing every {step}th point ({len(indices)} of {total} rows)*")
        lines.append("")
    else:
        times_show = times
        values_show = values

    lines.append("| Time (UTC) | Water Level (m) |")
    lines.append("| --- | --- |")
    for t, v in zip(times_show, values_show):
        lines.append(f"| {t} | {v:.3f} |")

    lines.append("")
    lines.append(f"*Data from {source}.*")
    return "\n".join(lines)


def format_station_table(
    stations: list[dict],
    title: str = "",
    metadata_lines: list[str] | None = None,
    extra_col: tuple[str, str] | None = None,
    source: str = "NOAA STOFS",
) -> str:
    """Format a list of station dicts as a markdown table.

    Args:
        stations: List of station dicts with id, name, state, lat, lon.
        title: Optional heading.
        metadata_lines: Optional lines shown below title.
        extra_col: Optional (key, header) tuple for an extra column.
        source: Attribution string.
    """
    lines: list[str] = []

    if title:
        lines.append(f"## {title}")

    if metadata_lines:
        for m in metadata_lines:
            lines.append(f"**{m}**")
        lines.append("")

    if extra_col:
        key, header = extra_col
        lines.append(f"| Station ID | Name | State | Lat | Lon | {header} |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for s in stations:
            lines.append(
                f"| {s.get('id','')} | {s.get('name','')} | {s.get('state','')} "
                f"| {s.get('lat','')} | {s.get('lon','')} | {s.get(key,'')} |"
            )
    else:
        lines.append("| Station ID | Name | State | Lat | Lon |")
        lines.append("| --- | --- | --- | --- | --- |")
        for s in stations:
            lines.append(
                f"| {s.get('id','')} | {s.get('name','')} | {s.get('state','')} "
                f"| {s.get('lat','')} | {s.get('lon','')} |"
            )

    lines.append("")
    lines.append(f"*{len(stations)} stations. Data from {source}.*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cycle resolution
# ---------------------------------------------------------------------------

async def resolve_latest_cycle(
    client,
    model: str,
    num_days: int = 2,
) -> tuple[str, str] | None:
    """Find the latest available STOFS cycle on AWS S3.

    Checks today and yesterday (or more days), newest cycle first.

    Args:
        client: STOFSClient instance.
        model: '2d_global' or '3d_atlantic'.
        num_days: Number of past days to check.

    Returns:
        (date_str, cycle_str) tuple (e.g., ('20260219', '12')), or None.
    """
    from datetime import timedelta
    from .models import MODEL_CYCLES

    cycles = MODEL_CYCLES.get(model, ["12"])
    today = datetime.now(timezone.utc)

    for day_offset in range(num_days):
        date = today - timedelta(days=day_offset)
        date_str = date.strftime("%Y%m%d")
        for cycle in cycles:
            url = client.build_station_url(model, date_str, cycle)
            if await client.check_file_exists(url):
                return date_str, cycle

    return None


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def handle_stofs_error(e: Exception, model: str = "", url: str = "") -> str:
    """Format an exception into a user-friendly STOFS error message.

    Args:
        e: The exception.
        model: Model name for context.
        url: URL that was being accessed.

    Returns:
        User-friendly error string.
    """
    import httpx

    model_label = f" ({model})" if model else ""

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return (
                f"STOFS file not found{model_label} (HTTP 404). "
                "The cycle may not be available yet or has been archived. "
                "Use stofs_list_cycles to check available forecast cycles."
            )
        if status == 403:
            return (
                f"AWS S3 access denied{model_label} (HTTP 403). "
                "The data may have been archived. Try a more recent date."
            )
        return (
            f"HTTP {status} error{model_label}. "
            "The STOFS S3 bucket may be temporarily unavailable. Please try again."
        )

    if isinstance(e, httpx.TimeoutException):
        return (
            f"Download timed out{model_label}. "
            "STOFS NetCDF files can be 2-10 MB and may be slow. "
            "Try again or use a different cycle."
        )

    if isinstance(e, ValueError):
        return str(e)

    if "NetCDF" in type(e).__name__ or "netCDF" in str(e):
        return (
            f"Error reading STOFS NetCDF file{model_label}. "
            "The file may be corrupted or the format may have changed. "
            "Try a different cycle using stofs_list_cycles."
        )

    return f"Unexpected error{model_label}: {type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Temp file cleanup
# ---------------------------------------------------------------------------

def cleanup_temp_file(filepath: Path | str | None) -> None:
    """Remove a temporary NetCDF file. Safe to call with None."""
    if filepath is None:
        return
    try:
        os.unlink(str(filepath))
    except OSError:
        pass
