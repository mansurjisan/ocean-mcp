"""Station discovery and metadata tools for NDBC buoys."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import NDBCClient, haversine_distance, handle_ndbc_error
from ..server import mcp


def _get_client(ctx: Context) -> NDBCClient:
    return ctx.request_context.lifespan_context["ndbc_client"]


def _format_station_line(s: dict) -> str:
    """Format a station dict as a one-line summary."""
    sid = s.get("id", "?")
    name = s.get("name", "Unknown")
    lat = s.get("lat")
    lon = s.get("lon")
    stype = s.get("type", "")

    coord = ""
    if lat is not None and lon is not None:
        lon_dir = "W" if lon < 0 else "E"
        coord = f"({lat:.3f}\u00b0N, {abs(lon):.3f}\u00b0{lon_dir})"

    parts = [sid, "-", name]
    if stype:
        parts.append(f"[{stype}]")
    if coord:
        parts.append(coord)
    return " ".join(parts)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ndbc_list_stations(
    ctx: Context,
    station_type: str | None = None,
    owner: str | None = None,
    has_met: bool | None = None,
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List active NDBC stations with optional filters.

    Args:
        station_type: Filter by platform type (e.g., 'buoy', 'fixed', 'dart', 'cman', 'tides', 'oilrig').
        owner: Filter by station owner string (case-insensitive substring match, e.g., 'NDBC', 'Environment Canada').
        has_met: If true, only stations with meteorological sensors.
        limit: Maximum stations to return (default 50).
        offset: Number of stations to skip for pagination (default 0).
    """
    try:
        client = _get_client(ctx)
        stations = await client.get_active_stations()

        if station_type:
            st_lower = station_type.lower()
            stations = [s for s in stations if s.get("type", "").lower() == st_lower]

        if owner:
            owner_lower = owner.lower()
            stations = [
                s for s in stations if owner_lower in s.get("owner", "").lower()
            ]

        if has_met is True:
            stations = [s for s in stations if s.get("met") == "y"]

        total = len(stations)
        page = stations[offset : offset + limit]

        lines = ["## NDBC Active Stations"]
        filters = []
        if station_type:
            filters.append(f"Type: {station_type}")
        if owner:
            filters.append(f"Owner: {owner}")
        if has_met is True:
            filters.append("Has met sensors")
        if filters:
            lines.append(f"**Filters**: {', '.join(filters)}")
        lines.append(
            f"**Showing**: {offset + 1}\u2013{offset + len(page)} of {total} stations"
        )
        lines.append("")

        for s in page:
            lines.append(f"- {_format_station_line(s)}")

        if offset + limit < total:
            lines.append(f"\n*Use offset={offset + limit} to see more.*")

        return "\n".join(lines)
    except Exception as e:
        return handle_ndbc_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ndbc_get_station(
    ctx: Context,
    station_id: str,
) -> str:
    """Get metadata for a specific NDBC station.

    Args:
        station_id: NDBC station ID (e.g., '41001', '46042', 'TPLM2').
    """
    try:
        client = _get_client(ctx)
        station = await client.get_station_metadata(station_id)

        if station is None:
            return f"Station {station_id.upper()} not found in active stations list. Verify the ID with ndbc_list_stations."

        lines = [f"## Station {station['id']}"]
        lines.append(f"**Name**: {station.get('name', 'Unknown')}")

        lat = station.get("lat")
        lon = station.get("lon")
        if lat is not None:
            lines.append(f"**Latitude**: {lat}")
        if lon is not None:
            lines.append(f"**Longitude**: {lon}")

        if station.get("type"):
            lines.append(f"**Type**: {station['type']}")
        if station.get("owner"):
            lines.append(f"**Owner**: {station['owner']}")
        if station.get("pgm"):
            lines.append(f"**Program**: {station['pgm']}")

        caps = []
        if station.get("met") == "y":
            caps.append("Meteorological")
        if station.get("currents") == "y":
            caps.append("Currents")
        if station.get("waterquality") == "y":
            caps.append("Water Quality")
        if station.get("dart") == "y":
            caps.append("DART Tsunami")
        if caps:
            lines.append(f"**Capabilities**: {', '.join(caps)}")

        return "\n".join(lines)
    except Exception as e:
        return handle_ndbc_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ndbc_find_nearest_stations(
    ctx: Context,
    latitude: float,
    longitude: float,
    radius_km: float = 200.0,
    station_type: str | None = None,
    has_met: bool | None = None,
    limit: int = 5,
) -> str:
    """Find NDBC stations nearest to a geographic coordinate.

    Args:
        latitude: Latitude in decimal degrees (e.g., 40.7).
        longitude: Longitude in decimal degrees (e.g., -74.0).
        radius_km: Search radius in kilometers (default 200).
        station_type: Optional filter by platform type (e.g., 'buoy').
        has_met: If true, only stations with meteorological sensors.
        limit: Maximum number of stations to return (default 5).
    """
    try:
        client = _get_client(ctx)
        stations = await client.get_active_stations()

        if station_type:
            st_lower = station_type.lower()
            stations = [s for s in stations if s.get("type", "").lower() == st_lower]

        if has_met is True:
            stations = [s for s in stations if s.get("met") == "y"]

        results = []
        for s in stations:
            slat = s.get("lat")
            slon = s.get("lon")
            if slat is None or slon is None:
                continue
            dist = haversine_distance(latitude, longitude, slat, slon)
            if dist <= radius_km:
                results.append((dist, s))

        results.sort(key=lambda x: x[0])
        results = results[:limit]

        lines = [f"## Nearest NDBC Stations to ({latitude:.4f}, {longitude:.4f})"]
        filters = []
        if station_type:
            filters.append(f"Type: {station_type}")
        if has_met is True:
            filters.append("Has met sensors")
        if filters:
            lines.append(f"**Filters**: {', '.join(filters)}")
        lines.append(f"**Radius**: {radius_km} km | **Found**: {len(results)}")
        lines.append("")

        for dist, s in results:
            lines.append(f"- {_format_station_line(s)} \u2014 **{dist:.1f} km**")

        if not results:
            lines.append(
                "No stations found within the specified radius. Try increasing radius_km."
            )

        return "\n".join(lines)
    except Exception as e:
        return handle_ndbc_error(e)
