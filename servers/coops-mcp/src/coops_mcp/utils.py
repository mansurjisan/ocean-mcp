"""Shared utilities: formatters, haversine, date helpers, error handlers."""

import json
import math
import re
from datetime import datetime, timedelta


def format_station_summary(station: dict) -> str:
    """Format a station dict into a readable one-liner."""
    sid = station.get("id", station.get("stationId", "?"))
    name = station.get("name", "Unknown")
    state = station.get("state", "")
    lat = station.get("lat", station.get("latitude", "?"))
    lng = station.get("lng", station.get("longitude", "?"))

    location = f"{name}, {state}" if state else name
    try:
        coord = (
            f"({float(lat):.4f}\u00b0N, {abs(float(lng)):.4f}\u00b0W)"
            if float(lng) < 0
            else f"({float(lat):.4f}\u00b0N, {float(lng):.4f}\u00b0E)"
        )
    except (ValueError, TypeError):
        coord = ""

    return f"{sid} - {location} {coord}".strip()


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute distance in km between two lat/lng points using the haversine formula."""
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def normalize_date(date_str: str) -> str:
    """Convert various date formats to CO-OPS format (yyyyMMdd or yyyyMMdd HH:mm).

    Accepts: YYYY-MM-DD, YYYY/MM/DD, YYYYMMDD, ISO 8601 with time, etc.
    """
    date_str = date_str.strip()

    # Already in CO-OPS format
    if re.match(r"^\d{8}$", date_str):
        return date_str
    if re.match(r"^\d{8} \d{2}:\d{2}$", date_str):
        return date_str

    # ISO 8601: 2024-10-01T14:30:00 or 2024-10-01 14:30
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y%m%d %H:%M")
        except ValueError:
            continue

    # Date only: 2024-10-01, 2024/10/01
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y%m%d")
        except ValueError:
            continue

    raise ValueError(
        f"Unrecognized date format: '{date_str}'. Use YYYY-MM-DD or YYYYMMDD."
    )


def validate_date_range(begin_date: str, end_date: str, max_days: int = 365) -> None:
    """Validate that a date range doesn't exceed the API limit.

    Raises ValueError with a clear message if it does.
    """

    # Parse the normalized dates (yyyyMMdd or yyyyMMdd HH:mm)
    def parse(d: str) -> datetime:
        d = d.strip()
        if len(d) == 8:
            return datetime.strptime(d, "%Y%m%d")
        return datetime.strptime(d, "%Y%m%d %H:%M")

    dt_begin = parse(begin_date)
    dt_end = parse(end_date)

    if dt_end < dt_begin:
        raise ValueError(f"end_date ({end_date}) is before begin_date ({begin_date}).")

    delta = dt_end - dt_begin
    if delta > timedelta(days=max_days):
        raise ValueError(
            f"Date range of {delta.days} days exceeds the maximum of {max_days} days. "
            f"Break your request into smaller chunks of {max_days} days or fewer."
        )


def format_tabular_data(
    data: list[dict],
    columns: list[tuple[str, str]],
    title: str = "",
    metadata_lines: list[str] | None = None,
    count_label: str = "records",
    max_rows: int = 2000,
) -> str:
    """Format a list of dicts as a markdown table.

    Args:
        data: List of row dicts (assumed chronological, oldest first).
        columns: List of (dict_key, display_header) pairs.
        title: Optional markdown heading.
        metadata_lines: Optional lines shown below the title.
        count_label: Label for the count footer.
        max_rows: Cap on rows rendered. A long 6-min range can be tens of
            thousands of records; rendering them all floods the model's
            context. When the data exceeds the cap, the most recent
            ``max_rows`` are kept and the footer says so.
    """
    lines: list[str] = []

    if title:
        lines.append(f"## {title}")

    if metadata_lines:
        lines.append(" | ".join(f"**{m}**" for m in metadata_lines))
        lines.append("")

    total = len(data)
    truncated = total > max_rows
    rows = data[-max_rows:] if truncated else data

    # Header
    headers = [col[1] for col in columns]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")

    # Rows
    for row in rows:
        cells = [str(row.get(col[0], "")) for col in columns]
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    if truncated:
        lines.append(
            f"*Showing the most recent {len(rows)} of {total} {count_label} "
            f"(truncated). Narrow the date range, use a coarser interval "
            f"(e.g. 'h' for hourly), or call with response_format='json' and a "
            f"higher max_records for the full series. Data from NOAA CO-OPS.*"
        )
    else:
        lines.append(f"*{len(rows)} {count_label} returned. Data from NOAA CO-OPS.*")

    return "\n".join(lines)


def format_json_response(
    data: dict,
    station_id: str = "",
    params: dict | None = None,
    max_records: int = 2000,
) -> str:
    """Format API response as a JSON string with a metadata wrapper.

    Caps the embedded record list to its most recent ``max_records`` entries
    (CO-OPS returns them oldest-first) so a long date range doesn't flood the
    model's context. ``record_count`` is the number actually returned;
    ``total_count`` and ``truncated`` make any trimming explicit.
    """
    # Locate the embedded record list across CO-OPS product shapes:
    #   observations / met     -> data["data"]
    #   tide predictions       -> data["predictions"]
    #   currents predictions   -> data["current_predictions"]["cp"]
    location: tuple[str, ...] = ()
    if isinstance(data.get("data"), list):
        location, records = ("data",), data["data"]
    elif isinstance(data.get("predictions"), list):
        location, records = ("predictions",), data["predictions"]
    elif isinstance(data.get("current_predictions"), dict) and isinstance(
        data["current_predictions"].get("cp"), list
    ):
        location, records = (
            ("current_predictions", "cp"),
            data["current_predictions"]["cp"],
        )
    else:
        records = []

    total = len(records)
    truncated = total > max_records
    if truncated:
        records = records[-max_records:]
        if location == ("data",):
            data = {**data, "data": records}
        elif location == ("predictions",):
            data = {**data, "predictions": records}
        elif location == ("current_predictions", "cp"):
            data = {
                **data,
                "current_predictions": {**data["current_predictions"], "cp": records},
            }

    wrapper: dict = {
        "station_id": station_id,
        "request_params": params or {},
        "truncated": truncated,
        "record_count": len(records),
        "total_count": total,
        "data": data,
    }
    if truncated:
        wrapper["hint"] = (
            f"Showing the most recent {len(records)} of {total} records. "
            "Narrow the date range, or use a coarser interval (e.g. 'h' for "
            "hourly), to retrieve the full series."
        )
    return json.dumps(wrapper, indent=2)


def handle_api_error(e: Exception) -> str:
    """Format an exception into a user-friendly error message with suggestions."""
    from .client import COOPSAPIError
    import httpx

    if isinstance(e, COOPSAPIError):
        msg = str(e)
        suggestions = []
        if "not found" in msg.lower() or "no station" in msg.lower():
            suggestions.append(
                "Verify the station ID with coops_list_stations or coops_find_nearest_stations."
            )
        if "no data" in msg.lower():
            suggestions.append(
                "The station may not have data for the requested period or product. Check available sensors with coops_get_station."
            )
        if "exceed" in msg.lower() or "range" in msg.lower():
            suggestions.append(
                "The date range may be too large. Max is 365 days (or 3650 for hilo predictions)."
            )
        suggestion_text = (
            " ".join(suggestions)
            if suggestions
            else "Check your parameters and try again."
        )
        return f"CO-OPS API Error: {msg}. {suggestion_text}"

    if isinstance(e, httpx.HTTPStatusError):
        return f"HTTP Error {e.response.status_code}: {e.response.reason_phrase}. The CO-OPS API may be temporarily unavailable."

    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. The CO-OPS API may be experiencing high load. Please try again."

    return f"Unexpected error: {type(e).__name__}: {e}"
