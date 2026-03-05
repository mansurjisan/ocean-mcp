"""Station discovery tools for NWS surface wind observations."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import WindsClient
from ..models import US_STATES
from ..server import mcp


def _get_client(ctx: Context) -> WindsClient:
    return ctx.request_context.lifespan_context["winds_client"]


def _format_nws_station(feature: dict) -> str:
    """Format a NWS GeoJSON station feature into a readable one-liner."""
    props = feature.get("properties", {})
    station_id = props.get("stationIdentifier", "?")
    name = props.get("name", "Unknown")
    elev = props.get("elevation", {}).get("value")
    coords = feature.get("geometry", {}).get("coordinates", [None, None])
    lon, lat = coords[0], coords[1]

    parts = [f"{station_id} - {name}"]
    if lat is not None and lon is not None:
        ns = "N" if lat >= 0 else "S"
        ew = "W" if lon < 0 else "E"
        parts.append(f"({abs(lat):.4f}\u00b0{ns}, {abs(lon):.4f}\u00b0{ew})")
    if elev is not None:
        parts.append(f"Elev: {elev:.0f}m")

    return " ".join(parts)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def winds_list_stations(
    ctx: Context,
    state: str,
    limit: int = 50,
    response_format: str = "markdown",
) -> str:
    """List NWS weather stations by US state.

    Returns ASOS, AWOS, and other NWS-affiliated surface observation stations.
    Station IDs are ICAO codes (e.g., KJFK, KORD, KLAX).

    Args:
        state: US state 2-letter code (e.g., 'NY', 'FL', 'CA').
        limit: Maximum number of stations to return (default 50).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        state_upper = state.upper()
        if state_upper not in US_STATES:
            return f"Validation Error: '{state}' is not a valid US state code. Use a 2-letter code like 'NY', 'FL', 'CA'."

        client = _get_client(ctx)
        data = await client.get_stations_by_state(state_upper, limit=limit)

        if response_format == "json":
            import json

            return json.dumps(data, indent=2)

        features = data.get("features", [])

        lines = [f"## NWS Stations — {US_STATES[state_upper]} ({state_upper})"]
        lines.append(f"**Showing**: {len(features)} stations")
        lines.append("")

        for f in features:
            lines.append(f"- {_format_nws_station(f)}")

        if not features:
            lines.append("No stations found for this state.")

        lines.append("")
        lines.append("*Data from NWS Weather.gov API.*")

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
async def winds_get_station(
    ctx: Context,
    station_id: str,
    response_format: str = "markdown",
) -> str:
    """Get detailed metadata for a specific NWS station.

    Args:
        station_id: ICAO station identifier (e.g., 'KJFK', 'KORD', 'KLAX').
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        data = await client.get_station(station_id)

        if response_format == "json":
            import json

            return json.dumps(data, indent=2)

        props = data.get("properties", {})
        coords = data.get("geometry", {}).get("coordinates", [None, None])
        lon, lat = coords[0], coords[1]
        elev = props.get("elevation", {}).get("value")

        lines = [f"## Station {props.get('stationIdentifier', station_id)}"]
        lines.append(f"**Name**: {props.get('name', 'Unknown')}")

        if lat is not None:
            lines.append(f"**Latitude**: {lat}")
        if lon is not None:
            lines.append(f"**Longitude**: {lon}")
        if elev is not None:
            lines.append(f"**Elevation**: {elev:.1f} m")
        if props.get("county"):
            lines.append(f"**County**: {props['county']}")
        if props.get("timeZone"):
            lines.append(f"**Timezone**: {props['timeZone']}")
        if props.get("forecast"):
            lines.append(f"**Forecast Office**: {props['forecast']}")

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
async def winds_find_nearest_stations(
    ctx: Context,
    latitude: float,
    longitude: float,
    limit: int = 5,
    response_format: str = "markdown",
) -> str:
    """Find NWS stations nearest to a geographic coordinate.

    Args:
        latitude: Latitude in decimal degrees (e.g., 40.7).
        longitude: Longitude in decimal degrees (e.g., -74.0).
        limit: Maximum number of stations to return (default 5).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        data = await client.get_nearest_stations(latitude, longitude, limit=limit)

        if response_format == "json":
            import json

            return json.dumps(data, indent=2)

        features = data.get("features", [])

        lines = [f"## Nearest Stations to ({latitude:.4f}, {longitude:.4f})"]
        lines.append(f"**Found**: {len(features)} stations")
        lines.append("")

        for i, f in enumerate(features, 1):
            lines.append(f"- {_format_nws_station(f)}")

        if not features:
            lines.append(
                "No stations found near this location. The NWS API may not cover this area."
            )

        lines.append("")
        lines.append("*Stations ordered by proximity. Data from NWS Weather.gov API.*")

        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


def _handle_error(e: Exception) -> str:
    """Format an exception into a user-friendly error message."""
    import httpx

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return "Error: Station not found. Verify the station ID (ICAO format, e.g., KJFK) using winds_list_stations or winds_find_nearest_stations."
        return f"HTTP Error {status}: {e.response.reason_phrase}. The NWS API may be temporarily unavailable."

    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. The NWS API may be experiencing high load. Please try again."

    if isinstance(e, WindsClient):
        return f"API Error: {e}"

    return f"Unexpected error: {type(e).__name__}: {e}"
