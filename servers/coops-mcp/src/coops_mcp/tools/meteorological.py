"""Meteorological observation tools."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import COOPSClient
from ..models import DateShorthand, Interval, MetProduct, TimeZone, Units
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


# Column definitions per met product
_MET_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "wind": [
        ("t", "Time"),
        ("s", "Speed"),
        ("d", "Direction (\u00b0)"),
        ("dr", "Compass"),
        ("g", "Gust"),
    ],
    "air_temperature": [("t", "Time"), ("v", "Air Temp")],
    "water_temperature": [("t", "Time"), ("v", "Water Temp")],
    "air_pressure": [("t", "Time"), ("v", "Pressure")],
    "humidity": [("t", "Time"), ("v", "Humidity (%)")],
    "conductivity": [("t", "Time"), ("v", "Conductivity")],
    "salinity": [("t", "Time"), ("v", "Salinity (PSU)")],
    "visibility": [("t", "Time"), ("v", "Visibility")],
    "air_gap": [("t", "Time"), ("v", "Air Gap")],
}


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def coops_get_meteorological(
    ctx: Context,
    station_id: str,
    product: MetProduct,
    begin_date: str | None = None,
    end_date: str | None = None,
    date: DateShorthand | None = None,
    units: Units = Units.METRIC,
    interval: Interval | None = None,
    time_zone: TimeZone = TimeZone.GMT,
    response_format: str = "markdown",
) -> str:
    """Retrieve meteorological observations from a CO-OPS station.

    Args:
        station_id: CO-OPS station ID (e.g., '8724580' for Key West, FL).
        product: Met data type — 'wind', 'air_temperature', 'water_temperature', 'air_pressure', 'humidity', 'conductivity', 'salinity', 'visibility', or 'air_gap'.
        begin_date: Start date (YYYY-MM-DD or YYYYMMDD).
        end_date: End date (YYYY-MM-DD or YYYYMMDD).
        date: Date shorthand — 'today', 'latest', or 'recent' (alternative to begin/end).
        units: Unit system — 'metric' or 'english' (default: metric).
        interval: Data interval — '6' (6-min) or 'h' (hourly).
        time_zone: Time zone — 'gmt', 'lst', or 'lst_ldt' (default: gmt).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)

        params: dict = {
            "station": station_id,
            "product": product.value,
            "units": units.value,
            "time_zone": time_zone.value,
        }

        if interval and interval in (Interval.SIX_MIN, Interval.HOURLY):
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

        records = data.get("data", [])
        columns = _MET_COLUMNS.get(product.value, [("t", "Time"), ("v", "Value")])

        title = f"{product.value.replace('_', ' ').title()} \u2014 Station {station_id}"
        meta = [f"Units: {units.value}", f"Timezone: {time_zone.value}"]

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
