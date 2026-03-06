"""Site discovery and metadata tools for USGS Water Services."""

import math

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import USGSClient
from ..models import US_STATE_CODES, format_parameter
from ..server import mcp


def _get_client(ctx: Context) -> USGSClient:
    return ctx.request_context.lifespan_context["usgs_client"]


def _handle_error(e: Exception) -> str:
    """Format an exception into a user-friendly error message."""
    import httpx

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return "Error: Site not found. Verify the 8-digit USGS site number."
        return f"HTTP Error {status}: The USGS API may be temporarily unavailable."
    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. The USGS API may be experiencing high load."
    return f"Unexpected error: {type(e).__name__}: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def usgs_find_sites(
    ctx: Context,
    state_code: str | None = None,
    bbox: str | None = None,
    site_type: str = "ST",
    parameter_code: str = "00060",
    limit: int = 20,
    response_format: str = "markdown",
) -> str:
    """Find USGS gauge stations by state or bounding box.

    Search for active USGS streamflow monitoring sites. Returns site ID, name,
    coordinates, and drainage area.

    Args:
        state_code: US state 2-letter code (e.g., 'MD', 'TX'). Either state_code or bbox required.
        bbox: Bounding box as 'west,south,east,north' decimal degrees. Either state_code or bbox required.
        site_type: Site type code — 'ST' (stream, default), 'LK' (lake), 'SP' (spring).
        parameter_code: USGS parameter code — '00060' (discharge, default) or '00065' (gage height).
        limit: Maximum number of sites to return (default 20).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        if not state_code and not bbox:
            return "Validation Error: Either 'state_code' or 'bbox' must be provided."

        if state_code:
            state_upper = state_code.upper()
            if state_upper not in US_STATE_CODES:
                return f"Validation Error: '{state_code}' is not a valid US state code."

        params: dict = {
            "siteType": site_type,
            "parameterCd": parameter_code,
            "siteStatus": "active",
            "hasDataTypeCd": "iv",
        }
        if state_code:
            params["stateCd"] = state_code.upper()
        if bbox:
            params["bBox"] = bbox

        client = _get_client(ctx)
        rows = await client.get_rdb("site", params)

        rows = rows[:limit]

        if response_format == "json":
            import json

            return json.dumps(rows, indent=2)

        param_label = format_parameter(parameter_code)
        location = US_STATE_CODES.get(state_code.upper(), bbox) if state_code else bbox
        lines = [f"## USGS Sites — {location}"]
        lines.append(f"**Parameter**: {param_label}")
        lines.append(f"**Showing**: {len(rows)} sites")
        lines.append("")

        if rows:
            lines.append("| Site ID | Name | Lat | Lon | Drainage Area (mi²) |")
            lines.append("|---------|------|-----|-----|---------------------|")
            for row in rows:
                site_no = row.get("site_no", "?")
                name = row.get("station_nm", "Unknown")
                lat = row.get("dec_lat_va", "—")
                lon = row.get("dec_long_va", "—")
                da = row.get("drain_area_va", "—")
                lines.append(f"| {site_no} | {name} | {lat} | {lon} | {da} |")
        else:
            lines.append("No active sites found matching criteria.")

        lines.append("")
        lines.append("*Data from USGS Water Services.*")
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
async def usgs_get_site_info(
    ctx: Context,
    site_number: str,
    response_format: str = "markdown",
) -> str:
    """Get detailed metadata for a specific USGS site.

    Returns full site details including name, coordinates, county, HUC code,
    drainage area, datum, and contributing drainage area.

    Args:
        site_number: 8-digit USGS site number (e.g., '01646500').
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        if not site_number.isdigit() or len(site_number) < 8:
            return "Validation Error: Site number must be at least 8 digits (e.g., '01646500')."

        client = _get_client(ctx)
        rows = await client.get_rdb(
            "site",
            {
                "sites": site_number,
                "siteOutput": "expanded",
            },
        )

        if not rows:
            return f"Error: No data found for site {site_number}."

        if response_format == "json":
            import json

            return json.dumps(rows[0], indent=2)

        row = rows[0]
        lines = [f"## USGS Site {row.get('site_no', site_number)}"]
        lines.append(f"**Name**: {row.get('station_nm', 'Unknown')}")

        lat = row.get("dec_lat_va")
        lon = row.get("dec_long_va")
        if lat and lon:
            lines.append(f"**Latitude**: {lat}")
            lines.append(f"**Longitude**: {lon}")

        field_map = {
            "county_cd": "County Code",
            "state_cd": "State Code",
            "huc_cd": "HUC Code",
            "drain_area_va": "Drainage Area (mi²)",
            "contrib_drain_area_va": "Contributing Drainage Area (mi²)",
            "alt_va": "Altitude (ft)",
            "alt_datum_cd": "Altitude Datum",
            "site_tp_cd": "Site Type",
            "agency_cd": "Agency",
        }
        for key, label in field_map.items():
            val = row.get(key)
            if val and val.strip():
                lines.append(f"**{label}**: {val}")

        lines.append("")
        lines.append("*Data from USGS Water Services.*")
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
async def usgs_find_nearest_sites(
    ctx: Context,
    latitude: float,
    longitude: float,
    radius_miles: float = 25.0,
    parameter_code: str = "00060",
    limit: int = 10,
    response_format: str = "markdown",
) -> str:
    """Find USGS sites near a geographic point.

    Searches for active streamflow sites within a radius of the given
    coordinates, sorted by distance.

    Args:
        latitude: Latitude in decimal degrees.
        longitude: Longitude in decimal degrees.
        radius_miles: Search radius in miles (default 25).
        parameter_code: USGS parameter code — '00060' (discharge, default) or '00065' (gage height).
        limit: Maximum number of sites to return (default 10).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        if not -90 <= latitude <= 90:
            return "Validation Error: Latitude must be between -90 and 90."
        if not -180 <= longitude <= 180:
            return "Validation Error: Longitude must be between -180 and 180."

        # Convert radius to approximate bounding box
        lat_delta = radius_miles / 69.0
        lon_delta = radius_miles / (69.0 * math.cos(math.radians(latitude)))
        west = longitude - lon_delta
        south = latitude - lat_delta
        east = longitude + lon_delta
        north = latitude + lat_delta
        bbox = f"{west:.4f},{south:.4f},{east:.4f},{north:.4f}"

        client = _get_client(ctx)
        rows = await client.get_rdb(
            "site",
            {
                "bBox": bbox,
                "siteType": "ST",
                "parameterCd": parameter_code,
                "siteStatus": "active",
                "hasDataTypeCd": "iv",
            },
        )

        # Compute distance and sort
        def _distance(row: dict) -> float:
            try:
                rlat = float(row.get("dec_lat_va", "0"))
                rlon = float(row.get("dec_long_va", "0"))
                dlat = rlat - latitude
                dlon = rlon - longitude
                return math.sqrt(dlat**2 + dlon**2)
            except (ValueError, TypeError):
                return float("inf")

        rows.sort(key=_distance)
        rows = rows[:limit]

        if response_format == "json":
            import json

            return json.dumps(rows, indent=2)

        lines = [f"## Nearest USGS Sites to ({latitude:.4f}, {longitude:.4f})"]
        lines.append(f"**Search radius**: {radius_miles} mi")
        lines.append(f"**Found**: {len(rows)} sites")
        lines.append("")

        if rows:
            lines.append("| Site ID | Name | Lat | Lon | Dist (approx) |")
            lines.append("|---------|------|-----|-----|----------------|")
            for row in rows:
                site_no = row.get("site_no", "?")
                name = row.get("station_nm", "Unknown")
                rlat = row.get("dec_lat_va", "—")
                rlon = row.get("dec_long_va", "—")
                dist = _distance(row) * 69.0  # rough degree-to-miles
                lines.append(
                    f"| {site_no} | {name} | {rlat} | {rlon} | {dist:.1f} mi |"
                )
        else:
            lines.append("No active sites found within the search radius.")

        lines.append("")
        lines.append("*Data from USGS Water Services.*")
        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)
