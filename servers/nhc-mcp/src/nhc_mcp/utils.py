"""Parsers, formatters, and helper utilities for NHC data."""

from __future__ import annotations

import json
import re
from datetime import datetime


# ---------------------------------------------------------------------------
# ArcGIS layer ID mapping
# ---------------------------------------------------------------------------

# Each storm "slot" in the NHC ArcGIS MapServer is offset by 26 layers.
# Slot order: AT1-AT5, EP1-EP5, CP1

_SLOT_ORDER = [
    "AT1", "AT2", "AT3", "AT4", "AT5",
    "EP1", "EP2", "EP3", "EP4", "EP5",
    "CP1",
]

# Base layer IDs for the first slot (AT1)
_LAYER_BASES = {
    "forecast_points": 6,
    "forecast_track": 7,
    "forecast_cone": 8,
    "watch_warning": 9,
    "past_track": 12,
}

_SLOT_OFFSET = 26


def get_arcgis_layer_id(bin_number: str, layer_type: str) -> int:
    """Get the ArcGIS MapServer layer ID for a storm slot and layer type.

    Args:
        bin_number: Storm slot identifier (e.g., 'AT1', 'EP2', 'CP1').
        layer_type: One of 'forecast_points', 'forecast_track', 'forecast_cone',
                    'watch_warning', 'past_track'.

    Returns:
        Integer layer ID.

    Raises:
        ValueError: If bin_number or layer_type is invalid.
    """
    bin_upper = bin_number.upper()
    if bin_upper not in _SLOT_ORDER:
        raise ValueError(
            f"Unknown bin_number '{bin_number}'. "
            f"Valid values: {', '.join(_SLOT_ORDER)}"
        )
    if layer_type not in _LAYER_BASES:
        raise ValueError(
            f"Unknown layer_type '{layer_type}'. "
            f"Valid values: {', '.join(_LAYER_BASES.keys())}"
        )

    slot_index = _SLOT_ORDER.index(bin_upper)
    base = _LAYER_BASES[layer_type]
    return base + slot_index * _SLOT_OFFSET


ARCGIS_BASE_URL = (
    "https://mapservices.weather.noaa.gov/tropical/rest/services"
    "/tropical/NHC_tropical_weather/MapServer"
)


def build_arcgis_query_url(layer_id: int, where: str = "1=1") -> str:
    """Build an ArcGIS MapServer query URL.

    Args:
        layer_id: MapServer layer ID.
        where: SQL WHERE clause (default returns all features).

    Returns:
        Full query URL.
    """
    return (
        f"{ARCGIS_BASE_URL}/{layer_id}/query"
        f"?where={where}&outFields=*&f=json&returnGeometry=true"
    )


# ---------------------------------------------------------------------------
# ATCF coordinate parsing
# ---------------------------------------------------------------------------

def parse_atcf_latlon(lat_str: str, lon_str: str) -> tuple[float, float]:
    """Parse ATCF latitude/longitude strings (tenths of degree with hemisphere).

    Examples:
        '281N', '0940W' → (28.1, -94.0)
        '125S', '1700E' → (-12.5, 170.0)

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


def parse_hurdat2_latlon(lat_str: str, lon_str: str) -> tuple[float, float]:
    """Parse HURDAT2 latitude/longitude strings (decimal degrees with hemisphere).

    HURDAT2 uses a different format from ATCF B-deck: values are already in
    decimal degrees (e.g., '23.8N') rather than tenths of degrees ('238N').

    Examples:
        '23.8N', '75.7W' → (23.8, -75.7)
        '12.5S', '170.0E' → (-12.5, 170.0)

    Args:
        lat_str: Latitude string (e.g., '23.8N').
        lon_str: Longitude string (e.g., '75.7W').

    Returns:
        (latitude, longitude) tuple in decimal degrees.
    """
    lat_str = lat_str.strip()
    lon_str = lon_str.strip()

    lat_hemi = lat_str[-1].upper()
    lat_val = float(lat_str[:-1])
    if lat_hemi == "S":
        lat_val = -lat_val

    lon_hemi = lon_str[-1].upper()
    lon_val = float(lon_str[:-1])
    if lon_hemi == "W":
        lon_val = -lon_val

    return lat_val, lon_val


# ---------------------------------------------------------------------------
# Storm ID parsing
# ---------------------------------------------------------------------------

def parse_storm_id(storm_id: str) -> tuple[str, int, int]:
    """Parse a storm identifier like 'AL092005' into components.

    Args:
        storm_id: Storm ID in format {basin}{number}{year} (e.g., 'AL092005').

    Returns:
        Tuple of (basin, number, year) — e.g., ('al', 9, 2005).

    Raises:
        ValueError: If the storm ID format is invalid.
    """
    storm_id = storm_id.strip().upper()
    match = re.match(r"^(AL|EP|CP)(\d{2})(\d{4})$", storm_id)
    if not match:
        raise ValueError(
            f"Invalid storm ID '{storm_id}'. "
            f"Expected format: AL092005, EP042023, etc."
        )
    basin = match.group(1).lower()
    number = int(match.group(2))
    year = int(match.group(3))
    return basin, number, year


# ---------------------------------------------------------------------------
# HURDAT2 parser
# ---------------------------------------------------------------------------

def parse_hurdat2(text: str) -> list[dict]:
    """Parse HURDAT2-format text into a list of storm dictionaries.

    Each storm dict contains:
        - id: Storm ID (e.g., 'AL092005')
        - name: Storm name (e.g., 'KATRINA')
        - num_entries: Number of track entries
        - track: List of track point dicts with keys:
            date, time, record_id, status, lat, lon, max_wind, min_pressure,
            ...plus radii fields

    Args:
        text: Raw HURDAT2 text content.

    Returns:
        List of storm dictionaries.
    """
    storms: list[dict] = []
    lines = text.strip().split("\n")

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # Header line: AL092005, KATRINA, 34,
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            i += 1
            continue

        # Check if this is a header line (storm ID pattern)
        if not re.match(r"^[A-Z]{2}\d{6}$", parts[0]):
            i += 1
            continue

        storm_id = parts[0]
        storm_name = parts[1].strip()
        try:
            num_entries = int(parts[2])
        except ValueError:
            i += 1
            continue

        track: list[dict] = []
        for j in range(1, num_entries + 1):
            if i + j >= len(lines):
                break
            track_line = lines[i + j].rstrip()
            fields = [f.strip() for f in track_line.split(",")]
            if len(fields) < 8:
                continue

            date_str = fields[0]  # YYYYMMDD
            time_str = fields[1]  # HHMM
            record_id = fields[2]  # L, W, etc.
            status = fields[3]  # HU, TS, TD, etc.
            lat_str = fields[4]  # e.g., '281N'
            lon_str = fields[5]  # e.g., '0940W'

            try:
                lat, lon = parse_hurdat2_latlon(lat_str, lon_str)
            except (ValueError, IndexError):
                lat, lon = None, None

            try:
                max_wind = int(fields[6]) if fields[6].strip() not in ("", "-999") else None
            except ValueError:
                max_wind = None

            try:
                min_pressure = int(fields[7]) if fields[7].strip() not in ("", "-999") else None
            except ValueError:
                min_pressure = None

            point = {
                "date": date_str,
                "time": time_str,
                "record_id": record_id,
                "status": status,
                "lat": lat,
                "lon": lon,
                "max_wind": max_wind,
                "min_pressure": min_pressure,
            }
            track.append(point)

        storms.append({
            "id": storm_id,
            "name": storm_name,
            "num_entries": num_entries,
            "track": track,
        })
        i += num_entries + 1

    return storms


# ---------------------------------------------------------------------------
# ATCF B-deck parser
# ---------------------------------------------------------------------------

def parse_atcf_bdeck(text: str) -> list[dict]:
    """Parse ATCF B-deck (best track) text into a list of track point dicts.

    Only includes analysis points (tau=0). Each dict contains:
        basin, cyclone_num, datetime, lat, lon, max_wind, min_pressure, status

    Args:
        text: Raw ATCF B-deck file content.

    Returns:
        List of track point dictionaries.
    """
    points: list[dict] = []

    for line in text.strip().split("\n"):
        if not line.strip():
            continue
        fields = [f.strip() for f in line.split(",")]
        if len(fields) < 12:
            continue

        # Only keep tau=0 (analysis/best track points)
        try:
            tau = int(fields[5])
        except (ValueError, IndexError):
            continue
        if tau != 0:
            continue

        basin = fields[0].strip()
        try:
            cyclone_num = int(fields[1])
        except ValueError:
            continue
        date_str = fields[2].strip()  # YYYYMMDDHH
        lat_str = fields[6].strip()
        lon_str = fields[7].strip()

        try:
            lat, lon = parse_atcf_latlon(lat_str, lon_str)
        except (ValueError, IndexError):
            continue

        try:
            max_wind = int(fields[8]) if fields[8].strip() else None
        except ValueError:
            max_wind = None

        try:
            min_pressure = int(fields[9]) if fields[9].strip() else None
        except ValueError:
            min_pressure = None

        status = fields[10].strip() if len(fields) > 10 else ""

        try:
            dt = datetime.strptime(date_str, "%Y%m%d%H")
            dt_str = dt.strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            dt_str = date_str

        points.append({
            "basin": basin,
            "cyclone_num": cyclone_num,
            "datetime": dt_str,
            "lat": lat,
            "lon": lon,
            "max_wind": max_wind,
            "min_pressure": min_pressure,
            "status": status,
        })

    return points


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_tabular_data(
    data: list[dict],
    columns: list[tuple[str, str]],
    title: str = "",
    metadata_lines: list[str] | None = None,
    count_label: str = "records",
    source: str = "NOAA NHC",
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

def handle_nhc_error(e: Exception, context: str = "") -> str:
    """Format an exception into a user-friendly error message with suggestions.

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
                "The storm may not exist or may not be active. "
                "Use nhc_get_active_storms to check current activity, or "
                "nhc_search_storms to find historical storms."
            )
        return (
            f"{prefix}HTTP {status}: {e.response.reason_phrase}. "
            "The NHC server may be temporarily unavailable. Please try again."
        )

    if isinstance(e, httpx.TimeoutException):
        return (
            f"{prefix}Request timed out. NHC/ArcGIS services can be slow "
            "during active hurricane season. Please try again."
        )

    if isinstance(e, ValueError):
        return f"{prefix}{e}"

    return f"{prefix}{type(e).__name__}: {e}"
