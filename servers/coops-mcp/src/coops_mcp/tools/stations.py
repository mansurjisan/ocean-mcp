"""Station discovery and metadata tools."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import COOPSClient
from ..models import StationType, Units
from ..server import mcp
from ..utils import format_station_summary, haversine_distance, handle_api_error


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
async def coops_list_stations(
    ctx: Context,
    station_type: StationType | None = None,
    state: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List CO-OPS stations, optionally filtered by type and/or state.

    Args:
        station_type: Filter by station type (e.g., 'waterlevels', 'currentpredictions', 'waterlevelsandmet').
        state: Filter by US state (2-letter code, e.g., 'NY', 'FL').
        limit: Maximum number of stations to return (default 50).
        offset: Number of stations to skip for pagination (default 0).
    """
    try:
        client = _get_client(ctx)
        params: dict = {}
        if station_type:
            params["type"] = station_type.value

        data = await client.fetch_metadata("stations.json", params)
        stations = data.get("stations", [])

        # Filter by state if provided
        if state:
            state_upper = state.upper()
            stations = [
                s for s in stations if s.get("state", "").upper() == state_upper
            ]

        total = len(stations)
        stations = stations[offset : offset + limit]

        lines = ["## CO-OPS Stations"]
        filters = []
        if station_type:
            filters.append(f"Type: {station_type.value}")
        if state:
            filters.append(f"State: {state.upper()}")
        if filters:
            lines.append(f"**Filters**: {', '.join(filters)}")
        lines.append(
            f"**Showing**: {offset + 1}\u2013{offset + len(stations)} of {total} stations"
        )
        lines.append("")

        for s in stations:
            lines.append(f"- {format_station_summary(s)}")

        if offset + limit < total:
            lines.append(f"\n*Use offset={offset + limit} to see more.*")

        return "\n".join(lines)
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
async def coops_get_station(
    ctx: Context,
    station_id: str,
    expand: list[str] | None = None,
    units: Units = Units.METRIC,
) -> str:
    """Get detailed information for a specific CO-OPS station.

    Args:
        station_id: CO-OPS station ID (e.g., '8518750' for The Battery, NY).
        expand: Optional list of resources to include: 'details', 'sensors', 'datums', 'floodlevels', 'harcon', 'benchmarks'.
        units: Unit system — 'metric' or 'english' (default: metric).
    """
    try:
        client = _get_client(ctx)
        params: dict = {"units": units.value}
        if expand:
            params["expand"] = ",".join(expand)

        data = await client.fetch_metadata(f"stations/{station_id}.json", params)

        # The metadata API nests station info under "stations" list
        station = data.get("stations", [data])[0] if "stations" in data else data

        lines = [f"## Station {station_id}"]
        lines.append(f"**Name**: {station.get('name', 'Unknown')}")
        if station.get("state"):
            lines.append(f"**State**: {station['state']}")
        lines.append(
            f"**Latitude**: {station.get('lat', station.get('latitude', '?'))}"
        )
        lines.append(
            f"**Longitude**: {station.get('lng', station.get('longitude', '?'))}"
        )

        if station.get("affiliations"):
            lines.append(f"**Affiliations**: {station['affiliations']}")
        if station.get("timezonecorr"):
            lines.append(f"**Timezone Offset**: {station['timezonecorr']} hours")

        # Expanded details
        if station.get("details"):
            details = station["details"]
            lines.append("\n### Details")
            for key in (
                "accepted",
                "epoch",
                "origyear",
                "meridian",
                "datum",
                "timezonecorr",
            ):
                if details.get(key):
                    lines.append(f"- **{key}**: {details[key]}")

        if station.get("sensors"):
            sensors = station["sensors"]
            lines.append("\n### Sensors")
            for sensor in sensors:
                lines.append(f"- {sensor.get('name', sensor.get('id', '?'))}")

        if station.get("datums"):
            datums = station["datums"]
            lines.append("\n### Datums")
            datum_list = (
                datums if isinstance(datums, list) else datums.get("datums", [])
            )
            for d in datum_list:
                lines.append(
                    f"- **{d.get('name', '?')}**: {d.get('value', '?')} {units.value}"
                )

        if station.get("floodlevels"):
            flood = station["floodlevels"]
            lines.append("\n### Flood Levels")
            if isinstance(flood, list):
                for f in flood:
                    lines.append(f"- **{f.get('name', '?')}**: {f.get('value', '?')}")
            elif isinstance(flood, dict):
                for key, val in flood.items():
                    if val:
                        lines.append(f"- **{key}**: {val}")

        return "\n".join(lines)
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
async def coops_find_nearest_stations(
    ctx: Context,
    latitude: float,
    longitude: float,
    radius_km: float = 50.0,
    station_type: StationType | None = None,
    limit: int = 5,
) -> str:
    """Find CO-OPS stations nearest to a geographic coordinate.

    Args:
        latitude: Latitude in decimal degrees (e.g., 40.7).
        longitude: Longitude in decimal degrees (e.g., -74.0).
        radius_km: Search radius in kilometers (default 50).
        station_type: Optional filter by station type (e.g., 'waterlevels').
        limit: Maximum number of stations to return (default 5).
    """
    try:
        client = _get_client(ctx)
        params: dict = {}
        if station_type:
            params["type"] = station_type.value

        data = await client.fetch_metadata("stations.json", params)
        stations = data.get("stations", [])

        # Compute distances
        results = []
        for s in stations:
            try:
                slat = float(s.get("lat", s.get("latitude", 0)))
                slng = float(s.get("lng", s.get("longitude", 0)))
            except (ValueError, TypeError):
                continue
            dist = haversine_distance(latitude, longitude, slat, slng)
            if dist <= radius_km:
                results.append((dist, s))

        results.sort(key=lambda x: x[0])
        results = results[:limit]

        lines = [f"## Nearest Stations to ({latitude:.4f}, {longitude:.4f})"]
        if station_type:
            lines.append(f"**Type filter**: {station_type.value}")
        lines.append(f"**Radius**: {radius_km} km | **Found**: {len(results)}")
        lines.append("")

        for dist, s in results:
            lines.append(f"- {format_station_summary(s)} \u2014 **{dist:.1f} km**")

        if not results:
            lines.append(
                "No stations found within the specified radius. Try increasing radius_km."
            )

        return "\n".join(lines)
    except Exception as e:
        return handle_api_error(e)
