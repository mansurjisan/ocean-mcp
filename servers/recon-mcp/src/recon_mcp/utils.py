"""Parsers, formatters, and helper utilities for reconnaissance data."""

from __future__ import annotations

import json
import re


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
