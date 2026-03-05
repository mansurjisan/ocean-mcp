"""Tools: ww3_get_buoy_observations, ww3_get_buoy_history."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import WW3Client
from ..server import mcp
from ..utils import (
    format_wave_observation_table,
    handle_ww3_error,
    parse_ndbc_realtime,
)


def _get_client(ctx: Context) -> WW3Client:
    return ctx.request_context.lifespan_context["ww3_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ww3_get_buoy_observations(
    ctx: Context,
    station_id: str,
    hours: int = 24,
    response_format: str = "markdown",
) -> str:
    """Get recent wave observations from an NDBC buoy.

    Fetches realtime standard meteorological data from NDBC including wave
    height, dominant period, average period, mean wave direction, wind speed,
    and wind direction. Data covers the last ~45 days at hourly intervals.

    Args:
        station_id: NDBC station ID (e.g., '41025', '46042', '44013').
        hours: Number of recent hours to return (default 24, max 1080).
        response_format: 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        hours = max(1, min(1080, hours))

        raw_text = await client.fetch_ndbc_realtime(station_id)
        records = parse_ndbc_realtime(raw_text)

        if not records:
            return (
                f"No observation data available for NDBC station '{station_id}'. "
                "Verify the station ID using ww3_find_buoys."
            )

        # Limit to requested hours (data is hourly, newest first)
        records = records[:hours]

        if response_format == "json":
            return json.dumps(
                {
                    "station_id": station_id,
                    "records": len(records),
                    "observations": records,
                },
                indent=2,
            )

        return format_wave_observation_table(records, station_id=station_id)

    except Exception as e:
        return handle_ww3_error(e, f"buoy {station_id}")


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ww3_get_buoy_history(
    ctx: Context,
    station_id: str,
    year: int,
    max_records: int = 500,
    response_format: str = "markdown",
) -> str:
    """Get historical annual wave observations from an NDBC buoy.

    Fetches archived standard meteorological data for a specific year from
    the NDBC historical archive. Useful for climatological analysis.

    Args:
        station_id: NDBC station ID (e.g., '41025', '46042').
        year: Year to fetch (e.g., 2023).
        max_records: Maximum records to return (default 500, max 5000).
        response_format: 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        max_records = max(1, min(5000, max_records))

        raw_text = await client.fetch_ndbc_history(station_id, year)
        records = parse_ndbc_realtime(raw_text)

        if not records:
            return (
                f"No historical data available for NDBC station '{station_id}' "
                f"in year {year}. The station may not have data for that year."
            )

        # Subsample if too many
        if len(records) > max_records:
            step = max(1, len(records) // max_records)
            records = records[::step]

        if response_format == "json":
            return json.dumps(
                {
                    "station_id": station_id,
                    "year": year,
                    "records": len(records),
                    "observations": records,
                },
                indent=2,
            )

        table = format_wave_observation_table(records, station_id=station_id)
        return f"### Historical Data — {year}\n\n{table}"

    except Exception as e:
        return handle_ww3_error(e, f"buoy {station_id} history {year}")
