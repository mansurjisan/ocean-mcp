"""Tools: nhc_get_best_track, nhc_search_storms."""

from __future__ import annotations

import json
from datetime import datetime

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import NHCClient
from ..models import Basin, classify_wind_speed
from ..server import mcp
from ..utils import (
    format_tabular_data,
    handle_nhc_error,
    parse_atcf_bdeck,
    parse_hurdat2,
    parse_storm_id,
)


def _get_client(ctx: Context) -> NHCClient:
    return ctx.request_context.lifespan_context["nhc_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def nhc_get_best_track(
    ctx: Context,
    storm_id: str,
    response_format: str = "markdown",
) -> str:
    """Get best track (observed path) data for a tropical cyclone.

    For recent storms (current/previous year), retrieves from ATCF B-deck files.
    For historical storms, retrieves from HURDAT2 archive (Atlantic 1851–2024,
    East Pacific 1949–2024).

    Args:
        storm_id: NHC storm identifier (e.g., 'AL092005' for Katrina, 'AL042024').
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        basin, number, year = parse_storm_id(storm_id)

        current_year = datetime.now().year
        track_points: list[dict] = []
        source = ""

        # Try ATCF B-deck for recent storms
        if year >= current_year - 1:
            try:
                text = await client.get_best_track_atcf(basin, number, year)
                track_points = parse_atcf_bdeck(text)
                source = "ATCF B-deck"
            except Exception:
                # Fall through to HURDAT2
                pass

        # Fall back to HURDAT2 for historical storms or if ATCF failed
        if not track_points:
            try:
                text = await client.get_hurdat2(basin)
                all_storms = parse_hurdat2(text)
                storm_id_upper = storm_id.upper()
                for storm in all_storms:
                    if storm["id"] == storm_id_upper:
                        # Convert HURDAT2 track points to common format
                        for pt in storm["track"]:
                            track_points.append(
                                {
                                    "datetime": f"{pt['date']} {pt['time']} UTC",
                                    "lat": pt["lat"],
                                    "lon": pt["lon"],
                                    "max_wind": pt["max_wind"],
                                    "min_pressure": pt["min_pressure"],
                                    "status": pt["status"],
                                }
                            )
                        source = "HURDAT2"
                        break
            except Exception as e2:
                return handle_nhc_error(
                    e2,
                    f"fetching best track for {storm_id}",
                )

        if not track_points:
            return (
                f"No best track data found for storm {storm_id}.\n\n"
                "Possible reasons:\n"
                "- The storm ID may be incorrect (format: AL092005)\n"
                "- ATCF B-deck files are only available for recent storms\n"
                "- HURDAT2 covers Atlantic (1851–2024) and East Pacific (1949–2024)\n\n"
                "Use nhc_search_storms to find valid storm IDs."
            )

        # Enrich with classification
        for pt in track_points:
            wind = pt.get("max_wind")
            if wind is not None:
                pt["category"] = classify_wind_speed(wind)
            else:
                pt["category"] = ""

        if response_format == "json":
            return json.dumps(
                {
                    "storm_id": storm_id.upper(),
                    "source": source,
                    "track_points": track_points,
                    "count": len(track_points),
                },
                indent=2,
            )

        columns = [
            ("datetime", "Date/Time"),
            ("lat", "Lat"),
            ("lon", "Lon"),
            ("max_wind", "Wind (kt)"),
            ("min_pressure", "Pressure (mb)"),
            ("status", "Status"),
            ("category", "Category"),
        ]

        return format_tabular_data(
            data=track_points,
            columns=columns,
            title=f"Best Track — {storm_id.upper()}",
            metadata_lines=[f"Source: {source}", f"Points: {len(track_points)}"],
            count_label="track points",
        )

    except ValueError as e:
        return handle_nhc_error(e, "parsing storm ID")
    except Exception as e:
        return handle_nhc_error(e, f"fetching best track for {storm_id}")


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def nhc_search_storms(
    ctx: Context,
    name: str | None = None,
    year: int | None = None,
    basin: Basin | None = None,
    min_wind: int | None = None,
    limit: int = 50,
    response_format: str = "markdown",
) -> str:
    """Search historical tropical cyclones in the HURDAT2 database.

    Searches the Atlantic (1851–2024) and East Pacific (1949–2024) hurricane
    databases. Filter by storm name, year, basin, and/or minimum wind speed.

    Args:
        name: Storm name to search for (case-insensitive, partial match). E.g., 'katrina'.
        year: Filter by year (e.g., 2005).
        basin: Filter by basin — 'al' (Atlantic), 'ep' (East Pacific), 'cp' (Central Pacific).
        min_wind: Minimum peak wind speed in knots (e.g., 64 for hurricanes, 96 for major).
        limit: Maximum number of results to return (default 50).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)

        if not any([name, year, basin, min_wind]):
            return (
                "Please provide at least one search filter:\n"
                "- `name`: Storm name (e.g., 'katrina')\n"
                "- `year`: Season year (e.g., 2005)\n"
                "- `basin`: 'al' (Atlantic) or 'ep' (East Pacific)\n"
                "- `min_wind`: Minimum peak wind in knots (64 = hurricane)\n\n"
                "Example: nhc_search_storms(name='katrina', basin='al')"
            )

        # Determine which basins to search
        if basin:
            basins_to_search = [basin.value]
        else:
            basins_to_search = ["al", "ep"]

        all_results: list[dict] = []

        for b in basins_to_search:
            text = await client.get_hurdat2(b)
            storms = parse_hurdat2(text)

            for storm in storms:
                # Filter by year
                if year is not None:
                    storm_year = int(storm["id"][4:8])
                    if storm_year != year:
                        continue

                # Filter by name
                if name is not None:
                    if name.upper() not in storm["name"].upper():
                        continue

                # Compute peak wind
                peak_wind = 0
                min_pres = 9999
                for pt in storm["track"]:
                    w = pt.get("max_wind")
                    p = pt.get("min_pressure")
                    if w is not None and w > peak_wind:
                        peak_wind = w
                    if p is not None and 0 < p < min_pres:
                        min_pres = p

                # Filter by min_wind
                if min_wind is not None and peak_wind < min_wind:
                    continue

                storm_year = int(storm["id"][4:8])
                all_results.append(
                    {
                        "id": storm["id"],
                        "name": storm["name"],
                        "year": storm_year,
                        "basin": storm["id"][:2],
                        "peak_wind": peak_wind if peak_wind > 0 else "N/A",
                        "min_pressure": min_pres if min_pres < 9999 else "N/A",
                        "category": classify_wind_speed(peak_wind)
                        if peak_wind > 0
                        else "N/A",
                        "track_points": len(storm["track"]),
                    }
                )

        # Sort by year descending, then peak wind descending
        all_results.sort(
            key=lambda r: (
                -(r["year"]),
                -(r["peak_wind"] if isinstance(r["peak_wind"], int) else 0),
            )
        )

        total = len(all_results)
        results = all_results[:limit]

        if not results:
            filters = []
            if name:
                filters.append(f"name='{name}'")
            if year:
                filters.append(f"year={year}")
            if basin:
                filters.append(f"basin='{basin.value}'")
            if min_wind:
                filters.append(f"min_wind={min_wind}")
            return (
                f"No storms found matching filters: {', '.join(filters)}.\n\n"
                "Try broadening your search. HURDAT2 covers:\n"
                "- Atlantic: 1851–2024\n"
                "- East Pacific: 1949–2024"
            )

        if response_format == "json":
            return json.dumps(
                {"storms": results, "total_matches": total, "showing": len(results)},
                indent=2,
            )

        # Build filter description
        filter_parts = []
        if name:
            filter_parts.append(f"Name: {name}")
        if year:
            filter_parts.append(f"Year: {year}")
        if basin:
            filter_parts.append(f"Basin: {basin.value.upper()}")
        if min_wind:
            filter_parts.append(f"Min wind: {min_wind} kt")

        metadata = filter_parts + [f"Showing {len(results)} of {total} matches"]

        columns = [
            ("id", "Storm ID"),
            ("name", "Name"),
            ("year", "Year"),
            ("basin", "Basin"),
            ("peak_wind", "Peak Wind (kt)"),
            ("min_pressure", "Min Pressure (mb)"),
            ("category", "Category"),
            ("track_points", "Track Pts"),
        ]

        return format_tabular_data(
            data=results,
            columns=columns,
            title="Storm Search Results",
            metadata_lines=metadata,
            count_label="storms",
        )

    except Exception as e:
        return handle_nhc_error(e, "searching storms")
