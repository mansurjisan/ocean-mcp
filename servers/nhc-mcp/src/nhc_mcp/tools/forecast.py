"""Tools: nhc_get_forecast_track, nhc_get_storm_watches_warnings."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import NHCClient
from ..server import mcp
from ..utils import (
    format_tabular_data,
    get_arcgis_layer_id,
    handle_nhc_error,
)


def _get_client(ctx: Context) -> NHCClient:
    return ctx.request_context.lifespan_context["nhc_client"]


async def _resolve_bin_number(client: NHCClient, storm_id: str) -> str | None:
    """Resolve a storm ID (e.g., 'AL052024') to its binNumber (e.g., 'AT5').

    Fetches CurrentStorms.json and matches by storm ID.

    Returns:
        binNumber string or None if not found.
    """
    storms = await client.get_active_storms()
    storm_id_upper = storm_id.upper()
    for storm in storms:
        # NHC CurrentStorms.json uses "id" field like "al052024"
        sid = storm.get("id", "").upper()
        if sid == storm_id_upper:
            return storm.get("binNumber")
    return None


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def nhc_get_forecast_track(
    ctx: Context,
    storm_id: str,
    response_format: str = "markdown",
) -> str:
    """Get the official NHC 5-day forecast track positions for an active storm.

    Retrieves forecast point data from the NHC ArcGIS MapServer including
    position (lat/lon), forecast time, maximum winds, development type,
    and Saffir-Simpson category for each forecast period (12h, 24h, etc.).

    Note: This only works for currently active storms. Use nhc_get_active_storms
    first to see available storms and their IDs.

    Args:
        storm_id: NHC storm identifier (e.g., 'AL052024', 'EP042023').
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)

        # Resolve storm_id to binNumber via active storms
        bin_number = await _resolve_bin_number(client, storm_id)
        if not bin_number:
            return (
                f"Storm '{storm_id}' not found among active storms.\n\n"
                "Use nhc_get_active_storms to see currently active cyclones. "
                "For historical storms, use nhc_get_best_track instead."
            )

        # Query Forecast Points layer
        layer_id = get_arcgis_layer_id(bin_number, "forecast_points")
        data = await client.query_arcgis_layer(layer_id)

        features = data.get("features", [])
        if not features:
            return (
                f"No forecast data available for storm {storm_id} "
                f"(bin {bin_number}). The advisory may be in preparation."
            )

        rows = []
        for feat in features:
            attrs = feat.get("attributes", {})
            geom = feat.get("geometry", {})
            row = {
                "stormname": attrs.get("stormname", ""),
                "tau": attrs.get("tau", ""),
                "datelbl": attrs.get("datelbl", ""),
                "lat": geom.get("y", attrs.get("lat", "")),
                "lon": geom.get("x", attrs.get("lon", "")),
                "maxwind": attrs.get("maxwind", ""),
                "gust": attrs.get("gust", ""),
                "mslp": attrs.get("mslp", ""),
                "tcdvlp": attrs.get("tcdvlp", ""),
                "ssnum": attrs.get("ssnum", ""),
                "dvlbl": attrs.get("dvlbl", ""),
                "advdate": attrs.get("advdate", ""),
                "advisnum": attrs.get("advisnum", ""),
            }
            rows.append(row)

        # Sort by forecast tau (hour)
        rows.sort(key=lambda r: int(r["tau"]) if str(r["tau"]).isdigit() else 0)

        if response_format == "json":
            return json.dumps(
                {
                    "storm_id": storm_id,
                    "bin_number": bin_number,
                    "forecast_points": rows,
                },
                indent=2,
            )

        metadata = [
            f"Storm: {storm_id}",
            f"Advisory: {rows[0].get('advisnum', 'N/A')}",
            f"Date: {rows[0].get('advdate', 'N/A')}",
        ]

        columns = [
            ("tau", "Tau (hr)"),
            ("datelbl", "Valid Time"),
            ("lat", "Lat"),
            ("lon", "Lon"),
            ("maxwind", "Max Wind (kt)"),
            ("gust", "Gust (kt)"),
            ("tcdvlp", "Type"),
            ("ssnum", "SS Cat"),
        ]

        return format_tabular_data(
            data=rows,
            columns=columns,
            title=f"Forecast Track — {rows[0].get('stormname', storm_id)}",
            metadata_lines=metadata,
            count_label="forecast points",
        )

    except Exception as e:
        return handle_nhc_error(e, "fetching forecast track")


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def nhc_get_storm_watches_warnings(
    ctx: Context,
    storm_id: str,
    response_format: str = "markdown",
) -> str:
    """Get active watches and warnings for an active tropical cyclone.

    Returns coastal watch/warning segments (Hurricane Warning, Tropical Storm
    Watch, etc.) from the NHC ArcGIS MapServer.

    Note: This only works for currently active storms with watches/warnings in
    effect. Use nhc_get_active_storms first to see available storms.

    Args:
        storm_id: NHC storm identifier (e.g., 'AL052024').
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)

        bin_number = await _resolve_bin_number(client, storm_id)
        if not bin_number:
            return (
                f"Storm '{storm_id}' not found among active storms.\n\n"
                "Use nhc_get_active_storms to see currently active cyclones."
            )

        layer_id = get_arcgis_layer_id(bin_number, "watch_warning")
        data = await client.query_arcgis_layer(layer_id)

        features = data.get("features", [])
        if not features:
            return (
                f"No watches or warnings currently in effect for storm {storm_id}.\n\n"
                "Watches/warnings may not yet be issued, or the storm may be "
                "too weak or too far from land."
            )

        rows = []
        for feat in features:
            attrs = feat.get("attributes", {})
            row = {
                "stormname": attrs.get("stormname", ""),
                "tcww": attrs.get("tcww", ""),
                "basin": attrs.get("basin", ""),
                "advdate": attrs.get("advdate", ""),
                "advisnum": attrs.get("advisnum", ""),
            }
            rows.append(row)

        if response_format == "json":
            return json.dumps(
                {
                    "storm_id": storm_id,
                    "bin_number": bin_number,
                    "watches_warnings": rows,
                },
                indent=2,
            )

        storm_name = rows[0].get("stormname", storm_id) if rows else storm_id
        metadata = [
            f"Storm: {storm_id}",
            f"Advisory: {rows[0].get('advisnum', 'N/A')}",
        ]

        columns = [
            ("tcww", "Watch/Warning Type"),
            ("stormname", "Storm"),
            ("basin", "Basin"),
            ("advdate", "Advisory Date"),
            ("advisnum", "Advisory #"),
        ]

        return format_tabular_data(
            data=rows,
            columns=columns,
            title=f"Watches & Warnings — {storm_name}",
            metadata_lines=metadata,
            count_label="watch/warning segments",
        )

    except Exception as e:
        return handle_nhc_error(e, "fetching watches/warnings")
