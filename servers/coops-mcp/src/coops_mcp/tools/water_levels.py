"""Water level observation and tide prediction tools."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import COOPSClient
from ..models import Datum, DateShorthand, Interval, TimeZone, Units
from ..server import mcp
from ..utils import (
    format_json_response,
    format_tabular_data,
    handle_api_error,
    normalize_date,
    validate_date_range,
)


def _get_client(ctx: Context) -> COOPSClient:
    return ctx.request_context.lifespan_context["coops_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def coops_get_water_levels(
    ctx: Context,
    station_id: str,
    begin_date: str | None = None,
    end_date: str | None = None,
    date: DateShorthand | None = None,
    datum: Datum = Datum.MLLW,
    units: Units = Units.METRIC,
    interval: Interval | None = None,
    time_zone: TimeZone = TimeZone.GMT,
    response_format: str = "markdown",
) -> str:
    """Retrieve observed water level data from a CO-OPS station.

    Use begin_date/end_date for a date range, or date='today'/'latest'/'recent' for shortcuts.
    Max range is 365 days per request.

    Args:
        station_id: CO-OPS station ID (e.g., '8518750' for The Battery, NY).
        begin_date: Start date (YYYY-MM-DD or YYYYMMDD format).
        end_date: End date (YYYY-MM-DD or YYYYMMDD format).
        date: Date shorthand — 'today', 'latest', or 'recent' (alternative to begin/end).
        datum: Vertical datum reference (default: MLLW). Options: MLLW, MHHW, MSL, NAVD, STND, MHW, MLW, MTL.
        units: Unit system — 'metric' or 'english' (default: metric).
        interval: Data interval — '6' (6-min), 'h' (hourly), 'hilo' (high/low only). Default is 6-min.
        time_zone: Time zone — 'gmt', 'lst', or 'lst_ldt' (default: gmt).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)

        # Determine product based on interval
        if interval == Interval.HILO:
            product = "high_low"
        elif interval == Interval.HOURLY:
            product = "hourly_height"
        else:
            product = "water_level"

        params: dict = {
            "station": station_id,
            "product": product,
            "datum": datum.value,
            "units": units.value,
            "time_zone": time_zone.value,
        }

        if interval and interval != Interval.HILO:
            params["interval"] = interval.value

        if date:
            params["date"] = date.value
        elif begin_date and end_date:
            bd = normalize_date(begin_date)
            ed = normalize_date(end_date)
            validate_date_range(bd, ed, max_days=365)
            params["begin_date"] = bd
            params["end_date"] = ed
        else:
            params["date"] = "recent"

        data = await client.fetch_data(params)

        if response_format == "json":
            return format_json_response(data, station_id, params)

        # Markdown formatting
        unit_label = "m" if units == Units.METRIC else "ft"

        if product == "high_low":
            records = data.get("data", [])
            columns = [
                ("t", "Time"),
                ("v", f"Level ({unit_label})"),
                ("ty", "Type"),
            ]
            title = f"Water Levels (High/Low) \u2014 Station {station_id}"
        else:
            records = data.get("data", [])
            columns = [
                ("t", "Time"),
                ("v", f"Level ({unit_label})"),
                ("s", "Sigma"),
                ("f", "Flags"),
            ]
            title = f"Water Levels \u2014 Station {station_id}"

        meta = [
            f"Datum: {datum.value}",
            f"Units: {units.value}",
            f"Timezone: {time_zone.value}",
        ]

        return format_tabular_data(
            records,
            columns,
            title=title,
            metadata_lines=meta,
            count_label="observations",
        )
    except ValueError as e:
        return f"Validation Error: {e}"
    except Exception as e:
        return handle_api_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def coops_get_tide_predictions(
    ctx: Context,
    station_id: str,
    begin_date: str,
    end_date: str,
    datum: Datum = Datum.MLLW,
    units: Units = Units.METRIC,
    interval: Interval | None = None,
    time_zone: TimeZone = TimeZone.GMT,
    response_format: str = "markdown",
) -> str:
    """Retrieve tide predictions for a CO-OPS station.

    Predictions are based on harmonic constituents — available for most water level stations.
    Max range: 365 days (or 3650 days for high/low interval).

    Args:
        station_id: CO-OPS station ID (e.g., '8518750' for The Battery, NY).
        begin_date: Start date (YYYY-MM-DD or YYYYMMDD format).
        end_date: End date (YYYY-MM-DD or YYYYMMDD format).
        datum: Vertical datum reference (default: MLLW).
        units: Unit system — 'metric' or 'english' (default: metric).
        interval: Prediction interval — '6' (6-min), 'h' (hourly), 'hilo' (high/low only). Default is 6-min.
        time_zone: Time zone — 'gmt', 'lst', or 'lst_ldt' (default: gmt).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)

        bd = normalize_date(begin_date)
        ed = normalize_date(end_date)
        max_days = 3650 if interval == Interval.HILO else 365
        validate_date_range(bd, ed, max_days=max_days)

        params: dict = {
            "station": station_id,
            "product": "predictions",
            "datum": datum.value,
            "units": units.value,
            "time_zone": time_zone.value,
            "begin_date": bd,
            "end_date": ed,
        }

        if interval:
            params["interval"] = interval.value

        data = await client.fetch_data(params)

        if response_format == "json":
            return format_json_response(data, station_id, params)

        unit_label = "m" if units == Units.METRIC else "ft"
        records = data.get("predictions", [])

        if interval == Interval.HILO:
            columns = [
                ("t", "Time"),
                ("v", f"Level ({unit_label})"),
                ("type", "Type"),
            ]
        else:
            columns = [
                ("t", "Time"),
                ("v", f"Level ({unit_label})"),
            ]

        title = f"Tide Predictions \u2014 Station {station_id}"
        meta = [
            f"Period: {begin_date} to {end_date}",
            f"Datum: {datum.value}",
            f"Units: {units.value}",
        ]

        return format_tabular_data(
            records,
            columns,
            title=title,
            metadata_lines=meta,
            count_label="predictions",
        )
    except ValueError as e:
        return f"Validation Error: {e}"
    except Exception as e:
        return handle_api_error(e)
