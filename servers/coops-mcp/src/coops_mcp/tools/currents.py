"""Currents observation and prediction tools."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import COOPSClient
from ..models import CurrentsProduct, DateShorthand, TimeZone, Units
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
async def coops_get_currents(
    ctx: Context,
    station_id: str,
    product: CurrentsProduct = CurrentsProduct.CURRENTS,
    begin_date: str | None = None,
    end_date: str | None = None,
    date: DateShorthand | None = None,
    units: Units = Units.METRIC,
    time_zone: TimeZone = TimeZone.GMT,
    bin_num: int | None = None,
    response_format: str = "markdown",
) -> str:
    """Retrieve current (water flow) observations or predictions from a CO-OPS currents station.

    Note: Currents stations use alphanumeric IDs (e.g., 'cb1401'), not the 7-digit numeric IDs used for water level stations.

    Args:
        station_id: CO-OPS currents station ID (e.g., 'cb1401').
        product: Data type — 'currents' for observations, 'currents_predictions' for predictions.
        begin_date: Start date (YYYY-MM-DD or YYYYMMDD).
        end_date: End date (YYYY-MM-DD or YYYYMMDD).
        date: Date shorthand — 'today', 'latest', or 'recent' (alternative to begin/end).
        units: Unit system — 'metric' or 'english' (default: metric).
        time_zone: Time zone — 'gmt', 'lst', or 'lst_ldt' (default: gmt).
        bin_num: Depth bin number for multi-bin stations (optional).
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

        if bin_num is not None:
            params["bin"] = str(bin_num)

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

        records = data.get(
            "data", data.get("current_predictions", data.get("predictions", []))
        )

        if product == CurrentsProduct.CURRENTS:
            columns = [
                ("t", "Time"),
                ("s", "Speed"),
                ("d", "Direction (\u00b0)"),
                ("b", "Bin"),
            ]
        else:
            columns = [
                ("Time", "Time"),
                ("Speed_kts", "Speed (kts)"),
                ("Velocity_Major", "Velocity Major"),
                ("meanEbbDir", "Ebb Dir"),
                ("meanFloodDir", "Flood Dir"),
            ]

        title = f"{'Currents' if product == CurrentsProduct.CURRENTS else 'Current Predictions'} \u2014 Station {station_id}"
        meta = [f"Units: {units.value}", f"Timezone: {time_zone.value}"]

        return format_tabular_data(
            records, columns, title=title, metadata_lines=meta, count_label="records"
        )
    except ValueError as e:
        return f"Validation Error: {e}"
    except Exception as e:
        return handle_api_error(e)
