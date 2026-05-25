"""Station discovery and metadata tools."""

from typing import Literal
from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import COOPSClient
from ..models import StationType, Units
from ..server import mcp
from ..utils import format_station_summary, haversine_distance, handle_api_error


def _get_client(ctx: Context) -> COOPSClient:
    return ctx.request_context.lifespan_context["coops_client"]


def _expanded_resource(value):
    """Return expanded sub-resource data, or None if it is only a ref stub.

    The CO-OPS mdapi returns sub-resources (details, sensors, datums,
    floodlevels) as a bare reference object ``{"self": "<url>"}`` unless the
    request passes ``?expand=<resource>``. Iterating a stub as if it were real
    data raised ``AttributeError: 'str' object has no attribute 'get'``
    (iterating a dict yields its string keys). Treat a stub (nothing beyond
    ``self``) as absent, and strip the ``self`` key from real payloads so it
    is never rendered as data.
    """
    if isinstance(value, list):
        return value or None
    if isinstance(value, dict):
        meaningful = {k: v for k, v in value.items() if k != "self"}
        return meaningful or None
    return None


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
        if limit < 1:
            return "Validation Error: limit must be >= 1."
        if offset < 0:
            return "Validation Error: offset must be >= 0."

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

        # Expanded sub-resources. Each is only present as real data when the
        # caller passed expand=<resource>; otherwise the mdapi returns a
        # {"self": url} stub which _expanded_resource() filters to None.
        details = _expanded_resource(station.get("details"))
        if details:
            detail_lines = [
                f"- **{key}**: {details[key]}"
                for key in (
                    "accepted",
                    "epoch",
                    "origyear",
                    "meridian",
                    "datum",
                    "timezonecorr",
                )
                if details.get(key)
            ]
            if detail_lines:
                lines.append("\n### Details")
                lines.extend(detail_lines)

        sensors_data = _expanded_resource(station.get("sensors"))
        if sensors_data:
            # Expanded shape is {"units": ..., "sensors": [...]}; be tolerant
            # of a bare list too.
            sensor_list = (
                sensors_data.get("sensors")
                if isinstance(sensors_data, dict)
                else sensors_data
            )
            if isinstance(sensor_list, list):
                rendered = [
                    f"- {s.get('name', s.get('id', '?'))}"
                    for s in sensor_list
                    if isinstance(s, dict)
                ]
                if rendered:
                    lines.append("\n### Sensors")
                    lines.extend(rendered)

        datums_data = _expanded_resource(station.get("datums"))
        if datums_data:
            if isinstance(datums_data, list):
                datum_list = datums_data
            elif isinstance(datums_data, dict):
                datum_list = datums_data.get("datums", [])
            else:
                datum_list = []
            rendered = [
                f"- **{d.get('name', '?')}**: {d.get('value', '?')} {units.value}"
                for d in datum_list
                if isinstance(d, dict)
            ]
            if rendered:
                lines.append("\n### Datums")
                lines.extend(rendered)

        flood = _expanded_resource(station.get("floodlevels"))
        if flood:
            if isinstance(flood, list):
                rendered = [
                    f"- **{f.get('name', '?')}**: {f.get('value', '?')}"
                    for f in flood
                    if isinstance(f, dict)
                ]
            elif isinstance(flood, dict):
                rendered = [f"- **{key}**: {val}" for key, val in flood.items() if val]
            else:
                rendered = []
            if rendered:
                lines.append("\n### Flood Levels")
                lines.extend(rendered)

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
    response_format: Literal["markdown", "geojson"] = "markdown",
) -> str:
    """Find CO-OPS stations nearest to a geographic coordinate.

    Args:
        latitude: Latitude in decimal degrees (e.g., 40.7).
        longitude: Longitude in decimal degrees (e.g., -74.0).
        radius_km: Search radius in kilometers (default 50).
        station_type: Optional filter by station type (e.g., 'waterlevels').
        limit: Maximum number of stations to return (default 5).
        response_format: Output format — 'markdown' (default) or 'geojson'
            (a FeatureCollection of Point features, coordinates [lon, lat]).
    """
    try:
        if not -90.0 <= latitude <= 90.0:
            return "Validation Error: latitude must be between -90 and 90."
        if not -180.0 <= longitude <= 180.0:
            return "Validation Error: longitude must be between -180 and 180."
        if radius_km <= 0:
            return "Validation Error: radius_km must be > 0."
        if limit < 1:
            return "Validation Error: limit must be >= 1."

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

        if response_format == "geojson":
            import json

            features = []
            for dist, s in results:
                try:
                    slng = float(s.get("lng", s.get("longitude")))
                    slat = float(s.get("lat", s.get("latitude")))
                except (TypeError, ValueError):
                    continue
                features.append(
                    {
                        "type": "Feature",
                        "geometry": {
                            "type": "Point",
                            "coordinates": [round(slng, 4), round(slat, 4)],
                        },
                        "properties": {
                            "id": s.get("id"),
                            "name": s.get("name"),
                            "state": s.get("state"),
                            "distance_km": round(dist, 1),
                        },
                    }
                )
            return json.dumps(
                {"type": "FeatureCollection", "features": features}, indent=2
            )

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
