"""Tools: ww3_list_grids, ww3_list_cycles, ww3_find_buoys."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import WW3Client
from ..models import VARIABLE_INFO, WAVE_GRIDS, WaveGrid
from ..server import mcp
from ..utils import handle_ww3_error, haversine, parse_ndbc_stations_xml


def _get_client(ctx: Context) -> WW3Client:
    return ctx.request_context.lifespan_context["ww3_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def ww3_list_grids(ctx: Context, response_format: str = "markdown") -> str:
    """List available GFS-Wave (WAVEWATCH III) model grids with resolution and domain info.

    Returns grid IDs, resolution, geographic coverage, forecast length, and
    available wave variables. Use this to choose a grid for ww3_get_forecast_at_point.

    Args:
        response_format: 'markdown' (default) or 'json'.
    """
    try:
        if response_format == "json":
            return json.dumps(
                {
                    grid_id: {
                        "name": info["name"],
                        "short_name": info["short_name"],
                        "resolution": info["resolution"],
                        "domain_desc": info["domain_desc"],
                        "domain": info["domain"],
                        "cycles": info["cycles"],
                        "forecast_hours": info["forecast_hours"],
                        "variables": list(VARIABLE_INFO.keys()),
                    }
                    for grid_id, info in WAVE_GRIDS.items()
                },
                indent=2,
            )

        lines = [
            "# GFS-Wave (WAVEWATCH III) Model Grids",
            "",
            "Global and regional wave forecast grids from NOAA's GFS-Wave system. "
            "Forecasts up to 16 days (384 hours), updated 4x daily.",
            "",
            "| Grid ID | Name | Resolution | Domain | Cycles | Forecast |",
            "| --- | --- | --- | --- | --- | --- |",
        ]

        for grid_id, info in WAVE_GRIDS.items():
            n_cycles = len(info["cycles"])
            lines.append(
                f"| `{grid_id}` | {info['name']} | {info['resolution']} "
                f"| {info['domain_desc'][:35]} | {n_cycles}x daily "
                f"| {info['forecast_hours']}h |"
            )

        lines += [
            "",
            "### Wave Variables",
            "",
            "| Variable | Description | Units |",
            "| --- | --- | --- |",
        ]
        for var_id, var_info in VARIABLE_INFO.items():
            lines.append(f"| `{var_id}` | {var_info['name']} | {var_info['units']} |")

        lines += [
            "",
            "Use `ww3_list_cycles` to check data availability. "
            "Use `ww3_get_forecast_at_point` to retrieve wave forecasts at a location.",
        ]

        return "\n".join(lines)

    except Exception as e:
        return handle_ww3_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ww3_list_cycles(
    ctx: Context,
    grid: WaveGrid = WaveGrid.GLOBAL_0P25,
    date: str | None = None,
    num_days: int = 2,
) -> str:
    """Check available GFS-Wave forecast cycles on NOAA servers.

    Checks AWS S3 for available GRIB2 files to determine which forecast
    cycles have been published. Useful before calling ww3_get_forecast_at_point.

    Args:
        grid: Wave grid to check (default: 'global.0p25').
        date: Specific date in YYYY-MM-DD format. Default: today UTC.
        num_days: Number of past days to check (1-7). Default: 2.
    """
    try:
        client = _get_client(ctx)
        num_days = max(1, min(7, num_days))

        grid_info = WAVE_GRIDS.get(grid.value, {})
        cycles = grid_info.get("cycles", ["00", "06", "12", "18"])
        grid_label = grid_info.get("name", grid.value)

        if date:
            try:
                end_date = datetime.strptime(date, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                return f"Invalid date format '{date}'. Use YYYY-MM-DD."
        else:
            end_date = datetime.now(timezone.utc)

        results = []
        for day_offset in range(num_days):
            check_date = end_date - timedelta(days=day_offset)
            date_str = check_date.strftime("%Y%m%d")
            date_label = check_date.strftime("%Y-%m-%d")

            for cycle in sorted(cycles, reverse=True):
                url = client.build_s3_grib_url(grid.value, date_str, cycle, 0)
                exists = await client.check_grib_exists(url)
                results.append(
                    {
                        "date": date_label,
                        "cycle": f"{cycle}z",
                        "status": "Available" if exists else "Not available",
                        "url": url if exists else "",
                    }
                )

        available = [r for r in results if r["status"] == "Available"]

        lines = [
            f"## GFS-Wave Forecast Cycles — {grid_label}",
            f"**Checking**: last {num_days} day(s) | "
            f"**Available**: {len(available)} of {len(results)} cycles",
            "",
            "| Date | Cycle | Status |",
            "| --- | --- | --- |",
        ]
        for r in results:
            lines.append(f"| {r['date']} | {r['cycle']} | {r['status']} |")

        lines.append("")
        if available:
            latest = available[0]
            lines.append(
                f"*Latest available: **{latest['date']} {latest['cycle']}**. "
                "Use ww3_get_forecast_at_point to retrieve wave data.*"
            )
        else:
            lines.append(
                "*No cycles found. GFS-Wave products typically arrive "
                "~4 hours after cycle time. Try again later or check a wider date range.*"
            )

        return "\n".join(lines)

    except Exception as e:
        return handle_ww3_error(e, grid.value)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ww3_find_buoys(
    ctx: Context,
    latitude: float,
    longitude: float,
    radius_km: float = 200.0,
    limit: int = 10,
    response_format: str = "markdown",
) -> str:
    """Find NDBC buoys near a geographic location.

    Searches the NDBC active stations registry for buoys within a specified
    radius of a lat/lon point. Returns station IDs, distances, and metadata.

    Args:
        latitude: Target latitude in decimal degrees.
        longitude: Target longitude in decimal degrees.
        radius_km: Search radius in kilometers (default 200).
        limit: Maximum number of buoys to return (default 10).
        response_format: 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        xml_text = await client.fetch_ndbc_active_stations()
        stations = parse_ndbc_stations_xml(xml_text)

        if not stations:
            return "Could not fetch or parse NDBC station list."

        # Compute distances and filter
        nearby = []
        for s in stations:
            dist = haversine(latitude, longitude, s["lat"], s["lon"])
            if dist <= radius_km:
                nearby.append({**s, "distance_km": round(dist, 1)})

        nearby.sort(key=lambda x: x["distance_km"])
        nearby = nearby[:limit]

        if response_format == "json":
            return json.dumps(
                {
                    "query_lat": latitude,
                    "query_lon": longitude,
                    "radius_km": radius_km,
                    "count": len(nearby),
                    "stations": nearby,
                },
                indent=2,
            )

        if not nearby:
            return (
                f"No NDBC buoys found within {radius_km} km of "
                f"({latitude:.4f}°N, {longitude:.4f}°E).\n\n"
                "Try increasing the search radius."
            )

        lines = [
            f"## NDBC Buoys Near ({latitude:.4f}°N, {longitude:.4f}°E)",
            f"**{len(nearby)} buoy(s)** found within {radius_km} km",
            "",
            "| Station | Name | Distance | Type | Lat | Lon |",
            "| --- | --- | --- | --- | --- | --- |",
        ]

        for s in nearby:
            lines.append(
                f"| `{s['id']}` | {s['name'][:30]} | {s['distance_km']:.1f} km "
                f"| {s['type']} | {s['lat']:.3f} | {s['lon']:.3f} |"
            )

        lines += [
            "",
            "Use `ww3_get_buoy_observations` with a station ID to fetch wave data.",
        ]

        return "\n".join(lines)

    except Exception as e:
        return handle_ww3_error(e)
