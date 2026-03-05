"""Observation retrieval tools for NWS surface wind data."""

import json
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import WindsClient
from ..models import (
    Units,
    degrees_to_compass,
    ms_to_knots,
    celsius_to_fahrenheit,
    pa_to_inhg,
    m_to_miles,
)
from ..server import mcp


def _get_client(ctx: Context) -> WindsClient:
    return ctx.request_context.lifespan_context["winds_client"]


def _safe_value(prop: dict | None) -> float | None:
    """Extract numeric value from a NWS observation property dict."""
    if prop is None:
        return None
    if isinstance(prop, dict):
        return prop.get("value")
    return None


def _format_wind_value(value: float | None, units: Units) -> str:
    """Format a wind speed value with unit conversion."""
    if value is None:
        return "---"
    if units == Units.ENGLISH:
        return f"{ms_to_knots(value):.1f}"
    return f"{value:.1f}"


def _format_temp_value(value: float | None, units: Units) -> str:
    """Format a temperature value with unit conversion."""
    if value is None:
        return "---"
    if units == Units.ENGLISH:
        return f"{celsius_to_fahrenheit(value):.1f}"
    return f"{value:.1f}"


def _format_pressure_value(value: float | None, units: Units) -> str:
    """Format a pressure value (Pa) with unit conversion."""
    if value is None:
        return "---"
    if units == Units.ENGLISH:
        return f"{pa_to_inhg(value):.2f}"
    # Convert Pa to hPa for metric
    return f"{value / 100.0:.1f}"


def _format_visibility_value(value: float | None, units: Units) -> str:
    """Format a visibility value with unit conversion."""
    if value is None:
        return "---"
    if units == Units.ENGLISH:
        return f"{m_to_miles(value):.1f}"
    # Convert m to km for metric
    return f"{value / 1000.0:.1f}"


def _format_observation_row(props: dict, units: Units) -> dict:
    """Extract and format key fields from a NWS observation properties dict."""
    timestamp = props.get("timestamp", "")
    if timestamp:
        # Shorten ISO timestamp for display
        timestamp = timestamp.replace("T", " ")[:19]

    wind_speed = _safe_value(props.get("windSpeed"))
    wind_dir = _safe_value(props.get("windDirection"))
    wind_gust = _safe_value(props.get("windGust"))
    temp = _safe_value(props.get("temperature"))
    pressure = _safe_value(props.get("barometricPressure"))
    visibility = _safe_value(props.get("visibility"))

    # NWS returns wind speed in km/h — convert to m/s first for internal consistency
    if wind_speed is not None:
        wind_speed_ms = wind_speed / 3.6
    else:
        wind_speed_ms = None
    if wind_gust is not None:
        wind_gust_ms = wind_gust / 3.6
    else:
        wind_gust_ms = None

    wind_unit = "kt" if units == Units.ENGLISH else "m/s"
    temp_unit = "\u00b0F" if units == Units.ENGLISH else "\u00b0C"
    pres_unit = "inHg" if units == Units.ENGLISH else "hPa"
    vis_unit = "mi" if units == Units.ENGLISH else "km"

    return {
        "time": timestamp,
        "wind_speed": _format_wind_value(wind_speed_ms, units),
        "wind_dir": str(int(wind_dir)) if wind_dir is not None else "---",
        "compass": degrees_to_compass(wind_dir),
        "wind_gust": _format_wind_value(wind_gust_ms, units),
        "temp": _format_temp_value(temp, units),
        "pressure": _format_pressure_value(pressure, units),
        "visibility": _format_visibility_value(visibility, units),
        "wind_unit": wind_unit,
        "temp_unit": temp_unit,
        "pres_unit": pres_unit,
        "vis_unit": vis_unit,
    }


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def winds_get_latest_observation(
    ctx: Context,
    station_id: str,
    units: Units = Units.METRIC,
    response_format: str = "markdown",
) -> str:
    """Get the most recent surface observation at a station.

    Returns wind speed, direction, gust, temperature, pressure, and visibility.

    Args:
        station_id: ICAO station identifier (e.g., 'KJFK', 'KORD').
        units: Unit system — 'metric' (m/s, °C, hPa) or 'english' (kt, °F, inHg). Default: metric.
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        data = await client.get_latest_observation(station_id)

        if response_format == "json":
            return json.dumps(data, indent=2)

        props = data.get("properties", {})
        row = _format_observation_row(props, units)

        lines = [f"## Latest Observation — {station_id.upper()}"]
        lines.append(f"**Time**: {row['time']}")
        lines.append(f"**Wind Speed**: {row['wind_speed']} {row['wind_unit']}")
        lines.append(f"**Wind Direction**: {row['wind_dir']}\u00b0 ({row['compass']})")
        lines.append(f"**Wind Gust**: {row['wind_gust']} {row['wind_unit']}")
        lines.append(f"**Temperature**: {row['temp']} {row['temp_unit']}")
        lines.append(f"**Pressure**: {row['pressure']} {row['pres_unit']}")
        lines.append(f"**Visibility**: {row['visibility']} {row['vis_unit']}")
        lines.append("")
        lines.append(f"*Data from NWS Weather.gov API. Units: {units.value}.*")

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def winds_get_observations(
    ctx: Context,
    station_id: str,
    hours: int = 24,
    units: Units = Units.METRIC,
    response_format: str = "markdown",
) -> str:
    """Get recent surface observations over a time window.

    Args:
        station_id: ICAO station identifier (e.g., 'KJFK').
        hours: Number of hours of observations to retrieve (default 24, max 168).
        units: Unit system — 'metric' or 'english' (default: metric).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        if hours < 1 or hours > 168:
            return "Validation Error: hours must be between 1 and 168 (7 days)."

        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=hours)
        start_iso = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        client = _get_client(ctx)
        data = await client.get_observations(station_id, start_iso, end_iso)

        if response_format == "json":
            return json.dumps(data, indent=2)

        features = data.get("features", [])
        if not features:
            return f"No observations found for {station_id.upper()} in the past {hours} hours."

        wind_unit = "kt" if units == Units.ENGLISH else "m/s"
        temp_unit = "\u00b0F" if units == Units.ENGLISH else "\u00b0C"

        lines = [f"## Observations — {station_id.upper()} (past {hours}h)"]
        lines.append(f"Wind: {wind_unit} | Temp: {temp_unit}")
        lines.append("")

        # Table header
        lines.append("| Time | Wind Spd | Dir | Compass | Gust | Temp |")
        lines.append("| --- | --- | --- | --- | --- | --- |")

        for f in features:
            props = f.get("properties", {})
            row = _format_observation_row(props, units)
            lines.append(
                f"| {row['time']} | {row['wind_speed']} | {row['wind_dir']} | {row['compass']} | {row['wind_gust']} | {row['temp']} |"
            )

        lines.append("")
        lines.append(
            f"*{len(features)} observations returned. Data from NWS Weather.gov API.*"
        )

        return "\n".join(lines)
    except ValueError as e:
        return f"Validation Error: {e}"
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def winds_get_history(
    ctx: Context,
    station_id: str,
    start_date: str,
    end_date: str,
    units: Units = Units.METRIC,
    response_format: str = "markdown",
) -> str:
    """Get historical ASOS wind data from the Iowa Environmental Mesonet archive.

    Provides access to historical surface observations dating back to ~2000.
    Uses 3-char FAA codes internally; K-prefix (ICAO) is stripped automatically.

    Args:
        station_id: Station identifier — ICAO (e.g., 'KJFK') or FAA (e.g., 'JFK').
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        units: Unit system — 'metric' or 'english' (default: metric).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        # Validate dates
        try:
            dt_start = datetime.strptime(start_date, "%Y-%m-%d")
            dt_end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return "Validation Error: Dates must be in YYYY-MM-DD format."

        if dt_end < dt_start:
            return f"Validation Error: end_date ({end_date}) is before start_date ({start_date})."

        delta = (dt_end - dt_start).days
        if delta > 366:
            return f"Validation Error: Date range of {delta} days exceeds the maximum of 366 days. Break your request into smaller chunks."

        client = _get_client(ctx)
        data = await client.get_iem_history(station_id, start_date, end_date)

        if response_format == "json":
            return json.dumps(data, indent=2)

        results = data.get("results", [])
        if not results:
            return f"No historical data found for {station_id} from {start_date} to {end_date}. Verify the station ID and date range."

        lines = [f"## Historical ASOS Data — {station_id.upper()}"]
        lines.append(f"**Period**: {start_date} to {end_date}")
        lines.append("")

        # Table header
        lines.append(
            "| Time (UTC) | Wind Spd (kt) | Dir (\u00b0) | Compass | Gust (kt) | Temp (\u00b0F) |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- |")

        for row in results[:200]:  # Cap display rows
            valid = row.get("valid", "")
            sknt = row.get("sknt", "")
            drct = row.get("drct", "")
            gust = row.get("gust_sknt", row.get("gust", ""))
            tmpf = row.get("tmpf", "")

            compass = ""
            if drct and drct != "M":
                try:
                    compass = degrees_to_compass(float(drct))
                except (ValueError, TypeError):
                    compass = ""

            # Convert if metric requested
            if units == Units.METRIC:
                try:
                    if sknt and sknt != "M":
                        sknt_val = float(sknt) * 0.514444  # kt to m/s
                        sknt = f"{sknt_val:.1f}"
                except (ValueError, TypeError):
                    pass
                try:
                    if gust and gust != "M":
                        gust_val = float(gust) * 0.514444
                        gust = f"{gust_val:.1f}"
                except (ValueError, TypeError):
                    pass
                try:
                    if tmpf and tmpf != "M":
                        tmpf_val = (float(tmpf) - 32.0) * 5.0 / 9.0
                        tmpf = f"{tmpf_val:.1f}"
                except (ValueError, TypeError):
                    pass

            sknt = str(sknt) if sknt and sknt != "M" else "---"
            drct = str(drct) if drct and drct != "M" else "---"
            gust = str(gust) if gust and gust != "M" else "---"
            tmpf = str(tmpf) if tmpf and tmpf != "M" else "---"

            lines.append(f"| {valid} | {sknt} | {drct} | {compass} | {gust} | {tmpf} |")

        if units == Units.METRIC:
            lines[3] = (
                "| Time (UTC) | Wind Spd (m/s) | Dir (\u00b0) | Compass | Gust (m/s) | Temp (\u00b0C) |"
            )

        total = len(results)
        lines.append("")
        suffix = " (showing first 200)" if total > 200 else ""
        lines.append(
            f"*{total} observations{suffix}. Data from Iowa Environmental Mesonet ASOS archive.*"
        )

        return "\n".join(lines)
    except ValueError as e:
        return f"Validation Error: {e}"
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def winds_get_daily_summary(
    ctx: Context,
    station_id: str,
    start_date: str,
    end_date: str,
    units: Units = Units.METRIC,
    response_format: str = "markdown",
) -> str:
    """Get daily wind statistics summary from IEM ASOS archive.

    Computes daily max/mean wind speed, max gust, and prevailing direction.

    Args:
        station_id: Station identifier — ICAO (e.g., 'KJFK') or FAA (e.g., 'JFK').
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        units: Unit system — 'metric' or 'english' (default: metric).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        # Validate dates
        try:
            dt_start = datetime.strptime(start_date, "%Y-%m-%d")
            dt_end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            return "Validation Error: Dates must be in YYYY-MM-DD format."

        if dt_end < dt_start:
            return f"Validation Error: end_date ({end_date}) is before start_date ({start_date})."

        delta = (dt_end - dt_start).days
        if delta > 366:
            return f"Validation Error: Date range of {delta} days exceeds the maximum of 366 days."

        client = _get_client(ctx)
        data = await client.get_iem_history(station_id, start_date, end_date)

        results = data.get("results", [])
        if not results:
            return f"No historical data found for {station_id} from {start_date} to {end_date}."

        # Group by date and compute daily summaries
        daily: dict[str, dict] = {}
        for row in results:
            valid = row.get("valid", "")
            date_str = valid[:10] if valid else ""
            if not date_str:
                continue

            if date_str not in daily:
                daily[date_str] = {
                    "speeds": [],
                    "gusts": [],
                    "dirs": [],
                }

            sknt = row.get("sknt")
            gust = row.get("gust_sknt", row.get("gust"))
            drct = row.get("drct")

            if sknt is not None and sknt != "M" and sknt != "":
                try:
                    daily[date_str]["speeds"].append(float(sknt))
                except (ValueError, TypeError):
                    pass
            if gust is not None and gust != "M" and gust != "":
                try:
                    daily[date_str]["gusts"].append(float(gust))
                except (ValueError, TypeError):
                    pass
            if drct is not None and drct != "M" and drct != "":
                try:
                    daily[date_str]["dirs"].append(float(drct))
                except (ValueError, TypeError):
                    pass

        summary_data = []
        for date_str in sorted(daily.keys()):
            d = daily[date_str]
            speeds = d["speeds"]
            gusts = d["gusts"]
            dirs = d["dirs"]

            mean_spd = sum(speeds) / len(speeds) if speeds else None
            max_spd = max(speeds) if speeds else None
            max_gust = max(gusts) if gusts else None

            # Prevailing direction: mode of compass directions
            if dirs:
                compass_dirs = [degrees_to_compass(deg) for deg in dirs]
                prevailing = max(set(compass_dirs), key=compass_dirs.count)
            else:
                prevailing = "---"

            summary_data.append(
                {
                    "date": date_str,
                    "mean_speed": mean_spd,
                    "max_speed": max_spd,
                    "max_gust": max_gust,
                    "prevailing_dir": prevailing,
                    "obs_count": len(speeds),
                }
            )

        if response_format == "json":
            # Convert for JSON
            for s in summary_data:
                if units == Units.METRIC:
                    if s["mean_speed"] is not None:
                        s["mean_speed"] = round(s["mean_speed"] * 0.514444, 1)
                    if s["max_speed"] is not None:
                        s["max_speed"] = round(s["max_speed"] * 0.514444, 1)
                    if s["max_gust"] is not None:
                        s["max_gust"] = round(s["max_gust"] * 0.514444, 1)
                    s["speed_unit"] = "m/s"
                else:
                    if s["mean_speed"] is not None:
                        s["mean_speed"] = round(s["mean_speed"], 1)
                    if s["max_speed"] is not None:
                        s["max_speed"] = round(s["max_speed"], 1)
                    if s["max_gust"] is not None:
                        s["max_gust"] = round(s["max_gust"], 1)
                    s["speed_unit"] = "kt"
            return json.dumps(
                {"station": station_id, "summaries": summary_data}, indent=2
            )

        spd_unit = "m/s" if units == Units.METRIC else "kt"
        convert = (lambda x: x * 0.514444) if units == Units.METRIC else (lambda x: x)

        lines = [f"## Daily Wind Summary — {station_id.upper()}"]
        lines.append(f"**Period**: {start_date} to {end_date}")
        lines.append("")
        lines.append(
            f"| Date | Mean ({spd_unit}) | Max ({spd_unit}) | Max Gust ({spd_unit}) | Prevailing Dir | Obs |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- |")

        for s in summary_data:
            mean = (
                f"{convert(s['mean_speed']):.1f}"
                if s["mean_speed"] is not None
                else "---"
            )
            mx = (
                f"{convert(s['max_speed']):.1f}"
                if s["max_speed"] is not None
                else "---"
            )
            gust = (
                f"{convert(s['max_gust']):.1f}" if s["max_gust"] is not None else "---"
            )
            lines.append(
                f"| {s['date']} | {mean} | {mx} | {gust} | {s['prevailing_dir']} | {s['obs_count']} |"
            )

        lines.append("")
        lines.append(
            f"*{len(summary_data)} days summarized. Data from Iowa Environmental Mesonet ASOS archive.*"
        )

        return "\n".join(lines)
    except ValueError as e:
        return f"Validation Error: {e}"
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def winds_compare_stations(
    ctx: Context,
    station_ids: list[str],
    units: Units = Units.METRIC,
    response_format: str = "markdown",
) -> str:
    """Compare latest wind observations across multiple stations.

    Args:
        station_ids: List of ICAO station IDs to compare (max 10, e.g., ['KJFK', 'KLGA', 'KEWR']).
        units: Unit system — 'metric' or 'english' (default: metric).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        if len(station_ids) > 10:
            return "Validation Error: Maximum 10 stations can be compared at once."
        if len(station_ids) < 2:
            return "Validation Error: At least 2 stations are required for comparison."

        client = _get_client(ctx)

        results = []
        errors = []
        for sid in station_ids:
            try:
                data = await client.get_latest_observation(sid)
                props = data.get("properties", {})
                row = _format_observation_row(props, units)
                row["station"] = sid.upper()
                results.append(row)
            except Exception as e:
                errors.append(f"{sid.upper()}: {type(e).__name__}")

        if response_format == "json":
            return json.dumps({"comparisons": results, "errors": errors}, indent=2)

        wind_unit = "kt" if units == Units.ENGLISH else "m/s"
        temp_unit = "\u00b0F" if units == Units.ENGLISH else "\u00b0C"

        lines = ["## Station Comparison"]
        lines.append("")
        lines.append(
            f"| Station | Wind Spd ({wind_unit}) | Dir | Compass | Gust ({wind_unit}) | Temp ({temp_unit}) | Time |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")

        for r in results:
            lines.append(
                f"| {r['station']} | {r['wind_speed']} | {r['wind_dir']} | {r['compass']} | {r['wind_gust']} | {r['temp']} | {r['time']} |"
            )

        if errors:
            lines.append("")
            lines.append("**Errors:**")
            for err in errors:
                lines.append(f"- {err}")

        lines.append("")
        lines.append(
            f"*{len(results)} stations compared. Data from NWS Weather.gov API.*"
        )

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


def _handle_error(e: Exception) -> str:
    """Format an exception into a user-friendly error message."""
    import httpx

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return "Error: Station not found. Verify the station ID (ICAO format, e.g., KJFK)."
        return f"HTTP Error {status}: {e.response.reason_phrase}. The API may be temporarily unavailable."

    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Please try again."

    return f"Unexpected error: {type(e).__name__}: {e}"
