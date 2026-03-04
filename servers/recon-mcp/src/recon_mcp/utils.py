"""Parsers, formatters, and helper utilities for reconnaissance data."""

from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Directory listing parser
# ---------------------------------------------------------------------------


def parse_directory_listing(html: str) -> list[dict]:
    """Parse an Apache-style HTML directory listing into file entries.

    Args:
        html: Raw HTML from an Apache directory index page.

    Returns:
        List of dicts with 'filename' and 'href' keys.
    """
    entries: list[dict] = []
    # Match <a href="...">...</a> links, skip parent directory and sorting links
    for match in re.finditer(
        r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>', html, re.IGNORECASE
    ):
        href = match.group(1)
        text = match.group(2).strip()

        # Skip parent dir, Apache sorting links, and header artifacts
        if href in ("../", "/", "?") or text in (
            "Parent Directory",
            "Name",
            "Last modified",
            "Size",
            "Description",
        ):
            continue
        if href.startswith("?") or href.startswith("/"):
            continue

        entries.append({"filename": text, "href": href})

    return entries


# ---------------------------------------------------------------------------
# HDOB parser
# ---------------------------------------------------------------------------


def parse_hdob_message(text: str) -> dict:
    """Parse an HDOB (High Density Observation) bulletin.

    HDOB format: WMO header lines followed by space-delimited observation
    records. Each record has 14 fields at 30-second intervals.
    Lat/lon are in DDMM format (degrees and minutes), NOT tenths.

    Args:
        text: Raw HDOB bulletin text.

    Returns:
        Dict with 'header' info and 'observations' list.
    """
    lines = text.strip().split("\n")
    header_info: dict = {}
    observations: list[dict] = []

    # Parse header lines
    header_lines: list[str] = []
    data_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Data lines start with YYYYMMDD + 6-digit time (HHMMSS), but the
        # HDOB header line also starts with YYYYMMDD followed by 4-digit time
        # and "HDOB". Distinguish by checking for "HDOB" keyword.
        if re.match(r"^\d{8}\s", stripped) and "HDOB" not in stripped:
            data_start = i
            break
        header_lines.append(stripped)

    # Extract aircraft ID and storm info from header
    for hl in header_lines:
        if "NOAA" in hl or "AF" in hl or "TEAL" in hl:
            header_info["agency_line"] = hl
        match = re.match(r"^(AHONT1|AHOPN1|URNT15|UZNT13)", hl)
        if match:
            header_info["wmo_header"] = hl
        # Look for the HDOB observation header line with aircraft ID
        ob_match = re.match(r"^(\d{8})\s+(\d{4})\s+(\w+)\s+HDOB\s+(\d+)", hl)
        if ob_match:
            header_info["date"] = ob_match.group(1)
            header_info["time"] = ob_match.group(2)
            header_info["aircraft"] = ob_match.group(3)
            header_info["ob_number"] = ob_match.group(4)

    # Parse observation records
    for line in lines[data_start:]:
        stripped = line.strip()
        if not stripped:
            continue
        # Skip non-data lines ($$, end markers, etc.)
        if stripped.startswith("$$") or stripped.startswith("NNNN"):
            break

        fields = stripped.split()
        if len(fields) < 14:
            continue

        # Validate first field is a date
        if not re.match(r"^\d{8}$", fields[0]):
            continue

        obs = _parse_hdob_record(fields)
        if obs:
            observations.append(obs)

    return {"header": header_info, "observations": observations}


def _parse_hdob_record(fields: list[str]) -> dict | None:
    """Parse a single HDOB observation record (14 fields).

    Fields: date, time, lat(DDMM), lon(DDDMM), static_pressure,
            gps_alt, extrap_slp, temp, dewpoint, wind_dir_speed,
            peak_fl_wind, sfmr_sfc_wind, sfmr_peak_wind, rain_flag/qc
    """
    if len(fields) < 14:
        return None

    date_str = fields[0]  # YYYYMMDD
    time_str = fields[1]  # HHMMSS

    # Parse lat/lon — DDMM format (degrees + minutes)
    lat = _parse_hdob_latlon(fields[2], is_lat=True)
    lon = _parse_hdob_latlon(fields[3], is_lat=False)

    obs: dict = {
        "date": date_str,
        "time": time_str,
        "lat": lat,
        "lon": lon,
        "static_pressure_mb": _parse_hdob_value(fields[4], scale=0.1),
        "geopotential_alt_m": _parse_hdob_value(fields[5]),
        "extrapolated_slp_mb": _parse_hdob_slp(fields[6]),
        "temp_c": _parse_hdob_value(fields[7], scale=0.1),
        "dewpoint_c": _parse_hdob_value(fields[8], scale=0.1),
    }

    # Wind direction/speed field: "DDD/SSS" format
    wind_parts = fields[9].split("/") if "/" in fields[9] else [fields[9], "///"]
    obs["fl_wind_dir_deg"] = (
        _parse_hdob_value(wind_parts[0]) if len(wind_parts) > 0 else None
    )
    obs["fl_wind_speed_kt"] = (
        _parse_hdob_value(wind_parts[1]) if len(wind_parts) > 1 else None
    )

    obs["peak_fl_wind_kt"] = _parse_hdob_value(fields[10])
    obs["sfmr_sfc_wind_kt"] = _parse_hdob_value(fields[11])
    obs["sfmr_peak_sfc_wind_kt"] = _parse_hdob_value(fields[12])
    obs["rain_flag"] = fields[13] if fields[13] != "///" else None

    return obs


def _parse_hdob_latlon(value: str, is_lat: bool) -> float | None:
    """Parse HDOB lat/lon in DDMM or DDDMM format (degrees + minutes).

    Examples:
        '2606N' → 26.1  (26 degrees, 06 minutes)
        '08015W' → -80.25  (80 degrees, 15 minutes)
    """
    if not value or value.startswith("///"):
        return None

    try:
        hemi = value[-1].upper()
        numeric = value[:-1]

        if is_lat:
            # DDMM format
            degrees = int(numeric[:-2])
            minutes = int(numeric[-2:])
        else:
            # DDDMM format
            degrees = int(numeric[:-2])
            minutes = int(numeric[-2:])

        result = degrees + minutes / 60.0
        if hemi in ("S", "W"):
            result = -result
        return round(result, 4)
    except (ValueError, IndexError):
        return None


def _parse_hdob_value(value: str, scale: float = 1.0) -> float | None:
    """Parse an HDOB numeric value. '///' means missing."""
    if not value or "///" in value:
        return None
    try:
        return float(value) * scale
    except ValueError:
        return None


def _parse_hdob_slp(value: str) -> float | None:
    """Parse HDOB extrapolated SLP (offset from 1000 mb, in tenths).

    Examples: '0150' → 1015.0 mb, '-0032' → 996.8 mb
    """
    if not value or "///" in value:
        return None
    try:
        offset = float(value) * 0.1
        return round(1000.0 + offset, 1)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# VDM parser
# ---------------------------------------------------------------------------


def parse_vdm_message(text: str) -> dict:
    """Parse a Vortex Data Message (VDM).

    VDMs contain lettered fields (A through U) with storm center fix data.
    Post-2018 format is parsed here.

    Args:
        text: Raw VDM bulletin text.

    Returns:
        Dict with header info and parsed fields.
    """
    lines = text.strip().split("\n")
    result: dict = {"raw_text": text}
    header_lines: list[str] = []

    # Extract header info
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        header_lines.append(stripped)
        # Look for REPNT2/REPPN2 header
        if re.match(r"^(URNT12|URPN12|REPNT2|REPPN2)", stripped):
            result["wmo_header"] = stripped
        # Storm identification line (e.g., "VORTEX DATA MESSAGE  AL142024")
        vdm_match = re.search(
            r"VORTEX\s+(?:DATA\s+)?MESSAGE\s+(\w+)", stripped, re.IGNORECASE
        )
        if vdm_match:
            result["storm_id"] = vdm_match.group(1).upper()
        # Observation line with storm name
        obs_match = re.search(r"OB\s+\d+", stripped)
        if obs_match:
            result["observation_line"] = stripped

    # Parse lettered fields
    full_text = "\n".join(lines)

    # A. Date/Time of center fix
    a_match = re.search(r"A\.\s*(\d{6})\s*UTC", full_text)
    if a_match:
        result["fix_time_utc"] = a_match.group(1)

    # B. Center fix coordinates
    b_match = re.search(r"B\.\s*(\d{3,4}[NS])\s+(\d{4,5}[EW])", full_text)
    if b_match:
        lat = _parse_vdm_latlon(b_match.group(1), is_lat=True)
        lon = _parse_vdm_latlon(b_match.group(2), is_lat=False)
        result["center_lat"] = lat
        result["center_lon"] = lon

    # C. Flight-level pressure/height at center
    c_match = re.search(
        r"C\.\s*(\d+)\s*MB?\s*/?\s*(\d+)\s*(?:M|FT|GP)", full_text, re.IGNORECASE
    )
    if c_match:
        result["fl_pressure_mb"] = int(c_match.group(1))
        result["fl_height"] = int(c_match.group(2))

    # D. Minimum SLP (extrapolated)
    d_match = re.search(r"D\.\s*(\d+)\s*MB", full_text, re.IGNORECASE)
    if d_match:
        result["min_slp_mb"] = int(d_match.group(1))

    # E. Eye/wall character or storm motion
    e_match = re.search(r"E\.\s*(.+?)(?:\n|$)", full_text)
    if e_match:
        result["field_e"] = e_match.group(1).strip()

    # H. Max SFMR surface wind inbound
    h_match = re.search(r"H\.\s*(\d+)\s*KT", full_text, re.IGNORECASE)
    if h_match:
        result["max_sfmr_inbound_kt"] = int(h_match.group(1))

    # J. Max flight-level wind inbound
    j_match = re.search(r"J\.\s*(\d+)\s*KT", full_text, re.IGNORECASE)
    if j_match:
        result["max_fl_wind_inbound_kt"] = int(j_match.group(1))

    # L. Max SFMR surface wind outbound
    l_match = re.search(r"L\.\s*(\d+)\s*KT", full_text, re.IGNORECASE)
    if l_match:
        result["max_sfmr_outbound_kt"] = int(l_match.group(1))

    # N. Max flight-level wind outbound
    n_match = re.search(r"N\.\s*(\d+)\s*KT", full_text, re.IGNORECASE)
    if n_match:
        result["max_fl_wind_outbound_kt"] = int(n_match.group(1))

    # S. Eye diameter/character
    s_match = re.search(r"S\.\s*(.+?)(?:\n|$)", full_text)
    if s_match:
        eye_text = s_match.group(1).strip()
        result["eye_character"] = eye_text
        diam_match = re.search(r"(\d+)\s*NM", eye_text, re.IGNORECASE)
        if diam_match:
            result["eye_diameter_nm"] = int(diam_match.group(1))

    return result


def _parse_vdm_latlon(value: str, is_lat: bool) -> float | None:
    """Parse VDM lat/lon (DDMM or DDDMM format with hemisphere character).

    Examples: '2606N' → 26.1, '08015W' → -80.25
    """
    if not value:
        return None
    try:
        hemi = value[-1].upper()
        numeric = value[:-1]
        degrees = int(numeric[:-2])
        minutes = int(numeric[-2:])
        result = degrees + minutes / 60.0
        if hemi in ("S", "W"):
            result = -result
        return round(result, 4)
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# ATCF f-deck parser
# ---------------------------------------------------------------------------


def parse_atcf_fix_record(line: str) -> dict | None:
    """Parse a single ATCF f-deck (fix) record.

    F-deck format is comma-delimited with fields for basin, storm number,
    date, fix type, latitude, longitude, wind, pressure, etc.

    Args:
        line: Single line from an f-deck file.

    Returns:
        Parsed record dict, or None if the line is invalid.
    """
    if not line.strip():
        return None

    fields = [f.strip() for f in line.split(",")]
    if len(fields) < 10:
        return None

    basin = fields[0]
    try:
        cyclone_num = int(fields[1])
    except ValueError:
        return None

    date_str = fields[2]  # YYYYMMDDHH
    fix_type = fields[3] if len(fields) > 3 else ""

    # Parse lat/lon (fields 6 and 7 in standard f-deck)
    lat, lon = None, None
    if len(fields) > 7 and fields[6] and fields[7]:
        try:
            lat, lon = parse_atcf_latlon(fields[6], fields[7])
        except (ValueError, IndexError):
            pass

    # Wind and pressure
    max_wind = None
    min_pressure = None
    if len(fields) > 8 and fields[8]:
        try:
            max_wind = int(fields[8])
        except ValueError:
            pass
    if len(fields) > 9 and fields[9]:
        try:
            min_pressure = int(fields[9])
        except ValueError:
            pass

    return {
        "basin": basin,
        "cyclone_num": cyclone_num,
        "datetime": date_str,
        "fix_type": fix_type,
        "lat": lat,
        "lon": lon,
        "max_wind_kt": max_wind,
        "min_pressure_mb": min_pressure,
    }


def parse_atcf_latlon(lat_str: str, lon_str: str) -> tuple[float, float]:
    """Parse ATCF latitude/longitude strings (tenths of degree with hemisphere).

    Examples:
        '281N', '0940W' -> (28.1, -94.0)
        '125S', '1700E' -> (-12.5, 170.0)

    Args:
        lat_str: Latitude string (e.g., '281N').
        lon_str: Longitude string (e.g., '0940W').

    Returns:
        (latitude, longitude) tuple in decimal degrees.
    """
    lat_str = lat_str.strip()
    lon_str = lon_str.strip()

    lat_hemi = lat_str[-1].upper()
    lat_val = float(lat_str[:-1]) / 10.0
    if lat_hemi == "S":
        lat_val = -lat_val

    lon_hemi = lon_str[-1].upper()
    lon_val = float(lon_str[:-1]) / 10.0
    if lon_hemi == "W":
        lon_val = -lon_val

    return lat_val, lon_val


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def format_tabular_data(
    data: list[dict],
    columns: list[tuple[str, str]],
    title: str = "",
    metadata_lines: list[str] | None = None,
    count_label: str = "records",
    source: str = "NOAA NHC Reconnaissance Archive",
) -> str:
    """Format a list of dicts as a markdown table.

    Args:
        data: List of row dicts.
        columns: List of (dict_key, display_header) pairs.
        title: Optional markdown heading.
        metadata_lines: Optional lines shown below the title.
        count_label: Label for the count footer.
        source: Data source attribution.
    """
    lines: list[str] = []

    if title:
        lines.append(f"## {title}")

    if metadata_lines:
        lines.append(" | ".join(f"**{m}**" for m in metadata_lines))
        lines.append("")

    # Header
    headers = [col[1] for col in columns]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")

    # Rows
    for row in data:
        cells = [str(row.get(col[0], "")) for col in columns]
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    lines.append(f"*{len(data)} {count_label} returned. Data from {source}.*")

    return "\n".join(lines)


def format_json_response(data: dict | list, context: str = "") -> str:
    """Format data as a JSON string with optional context."""
    wrapper: dict = {}
    if context:
        wrapper["context"] = context
    if isinstance(data, list):
        wrapper["record_count"] = len(data)
        wrapper["data"] = data
    else:
        wrapper.update(data)
    return json.dumps(wrapper, indent=2)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def handle_recon_error(e: Exception, context: str = "") -> str:
    """Format an exception into a user-friendly error message.

    Args:
        e: The exception to handle.
        context: Optional context about what operation was being attempted.

    Returns:
        User-friendly error message string.
    """
    import httpx

    prefix = f"Error during {context}: " if context else "Error: "

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return (
                f"{prefix}Resource not found (HTTP 404). "
                "The requested data may not exist for the specified "
                "year, basin, or storm. Check that the year has "
                "reconnaissance data available."
            )
        return (
            f"{prefix}HTTP {status}: {e.response.reason_phrase}. "
            "The NHC server may be temporarily unavailable. Please try again."
        )

    if isinstance(e, httpx.TimeoutException):
        return (
            f"{prefix}Request timed out. The NHC archive server can be slow. "
            "Please try again."
        )

    if isinstance(e, ValueError):
        return f"{prefix}{e}"

    return f"{prefix}{type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# SFMR utilities — haversine, NetCDF parsing, radial wind profile
# ---------------------------------------------------------------------------

EARTH_RADIUS_KM = 6371.0


def haversine(
    lat1: float,
    lon1: float,
    lat2: float | list | object,
    lon2: float | list | object,
) -> float | object:
    """Compute great-circle distance(s) in km using the haversine formula.

    Accepts scalars or numpy arrays for lat2/lon2 (vectorized).
    lat1/lon1 are the reference point (scalar).

    Args:
        lat1: Reference latitude (degrees).
        lon1: Reference longitude (degrees).
        lat2: Target latitude(s) (degrees).
        lon2: Target longitude(s) (degrees).

    Returns:
        Distance(s) in km. Scalar if inputs are scalar, array otherwise.
    """
    rlat1 = math.radians(lat1)
    rlon1 = math.radians(lon1)

    # Check if numpy arrays
    try:
        import numpy as np

        if isinstance(lat2, np.ndarray):
            rlat2 = np.radians(lat2)
            rlon2 = np.radians(lon2)
            dlat = rlat2 - rlat1
            dlon = rlon2 - rlon1
            a = (
                np.sin(dlat / 2) ** 2
                + math.cos(rlat1) * np.cos(rlat2) * np.sin(dlon / 2) ** 2
            )
            return EARTH_RADIUS_KM * 2 * np.arcsin(np.sqrt(a))
    except ImportError:
        pass

    # Scalar path
    rlat2 = math.radians(float(lat2))
    rlon2 = math.radians(float(lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))


def parse_sfmr_netcdf(filepath: str | Path) -> dict:
    """Parse an AOML SFMR NetCDF file and extract key variables.

    Args:
        filepath: Path to the .nc file.

    Returns:
        Dict with keys: 'datetime' (array of datetime objects),
        'lat', 'lon', 'sws' (surface wind speed, m/s),
        'srr' (surface rain rate, mm/hr) — all as numpy arrays,
        plus 'metadata' dict with global attributes.
    """
    import numpy as np
    from netCDF4 import Dataset

    ds = Dataset(str(filepath), "r")
    try:
        # Variable names can vary — try common names
        def _find_var(ds, candidates):
            for name in candidates:
                if name in ds.variables:
                    return ds.variables[name][:]
            return None

        date_var = _find_var(ds, ["DATE", "date", "Date"])
        time_var = _find_var(ds, ["TIME", "time", "Time"])
        lat = _find_var(ds, ["LAT", "lat", "Lat", "latitude"])
        lon = _find_var(ds, ["LON", "lon", "Lon", "longitude"])
        sws = _find_var(ds, ["SWS", "sws", "SurfaceWindSpeed", "surface_wind_speed"])
        srr = _find_var(ds, ["SRR", "srr", "SurfaceRainRate", "surface_rain_rate"])

        if lat is None or lon is None or sws is None:
            raise ValueError(
                f"Required variables not found. Available: {list(ds.variables.keys())}"
            )

        # Build datetime array from DATE (YYYYMMDD int) and TIME (HHMMSS float/int)
        datetimes = []
        if date_var is not None and time_var is not None:
            for d, t in zip(date_var, time_var):
                d_int = int(d)
                t_int = int(round(float(t)))
                year = d_int // 10000
                month = (d_int % 10000) // 100
                day = d_int % 100
                hour = t_int // 10000
                minute = (t_int % 10000) // 100
                second = t_int % 100
                try:
                    dt = datetime(
                        year, month, day, hour, minute, second, tzinfo=timezone.utc
                    )
                    datetimes.append(dt)
                except ValueError:
                    datetimes.append(None)
        else:
            datetimes = [None] * len(lat)

        # Extract metadata
        metadata = {}
        for attr in ds.ncattrs():
            try:
                metadata[attr] = str(ds.getncattr(attr))
            except Exception:
                pass

        # Convert masked arrays to regular arrays, filling masked with NaN
        lat_arr = np.ma.filled(lat, np.nan).astype(float)
        lon_arr = np.ma.filled(lon, np.nan).astype(float)
        sws_arr = np.ma.filled(sws, np.nan).astype(float)
        srr_arr = (
            np.ma.filled(srr, np.nan).astype(float)
            if srr is not None
            else np.full(len(lat_arr), np.nan)
        )

        return {
            "datetime": datetimes,
            "lat": lat_arr,
            "lon": lon_arr,
            "sws": sws_arr,
            "srr": srr_arr,
            "metadata": metadata,
            "n_obs": len(lat_arr),
        }
    finally:
        ds.close()


def parse_atcf_best_track(text: str) -> list[dict]:
    """Parse ATCF b-deck best track text into a list of track points.

    Args:
        text: Raw b-deck file content.

    Returns:
        List of dicts with 'datetime' (datetime obj), 'lat', 'lon',
        'max_wind_kt', 'min_slp_mb'.
    """
    track = []
    for line in text.strip().split("\n"):
        if not line.strip():
            continue
        fields = [f.strip() for f in line.split(",")]
        if len(fields) < 8:
            continue

        # Field 2: YYYYMMDDHH
        date_str = fields[2].strip()
        if len(date_str) < 10:
            continue
        try:
            dt = datetime.strptime(date_str[:10], "%Y%m%d%H")
            dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        # Fields 6,7: lat/lon in tenths with hemisphere
        try:
            lat, lon = parse_atcf_latlon(fields[6], fields[7])
        except (ValueError, IndexError):
            continue

        # Field 8: max sustained wind (kt)
        max_wind = None
        if len(fields) > 8 and fields[8]:
            try:
                max_wind = int(fields[8])
            except ValueError:
                pass

        # Field 9: min SLP (mb)
        min_slp = None
        if len(fields) > 9 and fields[9]:
            try:
                min_slp = int(fields[9])
            except ValueError:
                pass

        track.append(
            {
                "datetime": dt,
                "lat": lat,
                "lon": lon,
                "max_wind_kt": max_wind,
                "min_slp_mb": min_slp,
            }
        )

    # Sort by datetime
    track.sort(key=lambda p: p["datetime"])
    return track


def interpolate_track_position(
    track: list[dict], target_time: datetime
) -> tuple[float, float] | None:
    """Linearly interpolate a best track to a target time.

    Args:
        track: Sorted list of track dicts (from parse_atcf_best_track).
        target_time: Target datetime (UTC).

    Returns:
        (lat, lon) tuple, or None if target_time is outside track range.
    """
    if not track:
        return None

    # Ensure target_time is tz-aware
    if target_time.tzinfo is None:
        target_time = target_time.replace(tzinfo=timezone.utc)

    # Clamp to track bounds
    if target_time <= track[0]["datetime"]:
        return track[0]["lat"], track[0]["lon"]
    if target_time >= track[-1]["datetime"]:
        return track[-1]["lat"], track[-1]["lon"]

    # Find bracketing points
    for i in range(len(track) - 1):
        t0 = track[i]["datetime"]
        t1 = track[i + 1]["datetime"]
        if t0 <= target_time <= t1:
            dt_total = (t1 - t0).total_seconds()
            if dt_total == 0:
                return track[i]["lat"], track[i]["lon"]
            frac = (target_time - t0).total_seconds() / dt_total
            lat = track[i]["lat"] + frac * (track[i + 1]["lat"] - track[i]["lat"])
            lon = track[i]["lon"] + frac * (track[i + 1]["lon"] - track[i]["lon"])
            return lat, lon

    return None


def compute_radial_wind_profile(
    sfmr_data: dict,
    track: list[dict],
    bin_size_km: float = 5.0,
    max_radius_km: float = 500.0,
) -> list[dict]:
    """Bin SFMR surface wind speed by radial distance from storm center.

    For each valid SFMR observation, interpolates the best track to get
    the storm center position, computes haversine distance, and bins
    by radius.

    Args:
        sfmr_data: Output of parse_sfmr_netcdf().
        track: Output of parse_atcf_best_track().
        bin_size_km: Radial bin width in km (default 5).
        max_radius_km: Maximum radius to include (default 500).

    Returns:
        List of dicts, one per bin, with keys: 'radius_min_km',
        'radius_max_km', 'mean_wind_ms', 'max_wind_ms', 'min_wind_ms',
        'samples'.
    """
    import numpy as np

    datetimes = sfmr_data["datetime"]
    lats = sfmr_data["lat"]
    lons = sfmr_data["lon"]
    sws = sfmr_data["sws"]

    # Build arrays of (radius, wind_speed) for valid observations
    radii = []
    winds = []

    for i in range(len(lats)):
        # Skip invalid observations
        if np.isnan(lats[i]) or np.isnan(lons[i]) or np.isnan(sws[i]):
            continue
        if sws[i] < 0:
            continue
        if datetimes[i] is None:
            continue

        center = interpolate_track_position(track, datetimes[i])
        if center is None:
            continue

        clat, clon = center
        dist = haversine(clat, clon, lats[i], lons[i])

        if dist <= max_radius_km:
            radii.append(dist)
            winds.append(sws[i])

    if not radii:
        return []

    radii = np.array(radii)
    winds = np.array(winds)

    # Bin by radius
    n_bins = int(max_radius_km / bin_size_km)
    bins: list[dict] = []

    for b in range(n_bins):
        r_min = b * bin_size_km
        r_max = (b + 1) * bin_size_km
        mask = (radii >= r_min) & (radii < r_max)
        count = int(np.sum(mask))

        if count == 0:
            continue

        bin_winds = winds[mask]
        bins.append(
            {
                "radius_min_km": r_min,
                "radius_max_km": r_max,
                "mean_wind_ms": round(float(np.mean(bin_winds)), 1),
                "max_wind_ms": round(float(np.max(bin_winds)), 1),
                "min_wind_ms": round(float(np.min(bin_winds)), 1),
                "samples": count,
            }
        )

    return bins


def cleanup_temp_file(filepath: Path | str | None) -> None:
    """Remove a temporary file. Safe to call with None."""
    if filepath is None:
        return
    try:
        os.unlink(str(filepath))
    except OSError:
        pass
