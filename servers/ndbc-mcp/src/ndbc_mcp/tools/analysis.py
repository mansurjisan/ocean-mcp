"""Analysis tools for NDBC buoy data — daily summaries and station comparisons."""

import json
from collections import defaultdict
from typing import Any

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import NDBCClient, handle_ndbc_error
from ..models import COLUMN_LABELS, SUMMARY_VARIABLES
from ..server import mcp


def _get_client(ctx: Context) -> NDBCClient:
    return ctx.request_context.lifespan_context["ndbc_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ndbc_get_daily_summary(
    ctx: Context,
    station_id: str,
    days: int = 7,
    variables: list[str] | None = None,
    response_format: str = "markdown",
) -> str:
    """Get daily min/max/mean statistics for key variables over recent days.

    Args:
        station_id: NDBC station ID (e.g., '41001', '46042').
        days: Number of days to summarize (default 7, max 45).
        variables: Variables to include (default: WSPD, GST, WVHT, DPD, PRES, ATMP, WTMP).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        if days < 1 or days > 45:
            return "Validation Error: days must be between 1 and 45."

        client = _get_client(ctx)
        columns, records = await client.get_observations(station_id, hours=days * 24)

        if not records:
            return f"No observations found for station {station_id.upper()} in the past {days} days."

        # Determine which variables to summarize
        data_cols = columns[5:]
        if variables:
            sum_vars = [v.upper() for v in variables if v.upper() in data_cols]
            if not sum_vars:
                avail = ", ".join(data_cols)
                return f"None of the requested variables found. Available: {avail}"
        else:
            sum_vars = [v for v in SUMMARY_VARIABLES if v in data_cols]

        if not sum_vars:
            return f"No summarizable variables found for station {station_id.upper()}."

        # Group by date
        daily: dict[str, dict[str, list[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for r in records:
            dt = r.get("datetime")
            if dt is None:
                continue
            date_key = dt.strftime("%Y-%m-%d")
            for var in sum_vars:
                val = r.get(var)
                if val is not None and isinstance(val, (int, float)):
                    daily[date_key][var].append(val)

        if not daily:
            return f"No valid data to summarize for station {station_id.upper()}."

        summaries = []
        for date_key in sorted(daily.keys()):
            day_data = daily[date_key]
            summary: dict[str, Any] = {"date": date_key}
            for var in sum_vars:
                vals = day_data.get(var, [])
                if vals:
                    summary[f"{var}_min"] = round(min(vals), 1)
                    summary[f"{var}_max"] = round(max(vals), 1)
                    summary[f"{var}_mean"] = round(sum(vals) / len(vals), 1)
                    summary[f"{var}_count"] = len(vals)
                else:
                    summary[f"{var}_min"] = None
                    summary[f"{var}_max"] = None
                    summary[f"{var}_mean"] = None
                    summary[f"{var}_count"] = 0
            summaries.append(summary)

        if response_format == "json":
            return json.dumps(
                {
                    "station": station_id.upper(),
                    "days": days,
                    "variables": sum_vars,
                    "summaries": summaries,
                },
                indent=2,
            )

        # Markdown — one table per variable
        lines = [f"## Daily Summary \u2014 {station_id.upper()} ({days} days)"]
        lines.append("")

        for var in sum_vars:
            label = COLUMN_LABELS.get(var, var)
            lines.append(f"### {label}")
            lines.append("| Date | Min | Max | Mean | Obs |")
            lines.append("| --- | --- | --- | --- | --- |")
            for s in summaries:
                mn = s.get(f"{var}_min")
                mx = s.get(f"{var}_max")
                mean = s.get(f"{var}_mean")
                cnt = s.get(f"{var}_count", 0)
                mn_s = f"{mn}" if mn is not None else "---"
                mx_s = f"{mx}" if mx is not None else "---"
                mean_s = f"{mean}" if mean is not None else "---"
                lines.append(f"| {s['date']} | {mn_s} | {mx_s} | {mean_s} | {cnt} |")
            lines.append("")

        lines.append(
            f"*{len(summaries)} days summarized. Data from NOAA NDBC realtime2.*"
        )

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
async def ndbc_compare_stations(
    ctx: Context,
    station_ids: list[str],
    response_format: str = "markdown",
) -> str:
    """Compare latest observations from multiple NDBC stations side by side.

    Args:
        station_ids: List of NDBC station IDs to compare (2-10 stations, e.g., ['41001', '41002', '44013']).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        if len(station_ids) < 2:
            return "Validation Error: At least 2 stations are required for comparison."
        if len(station_ids) > 10:
            return "Validation Error: Maximum 10 stations can be compared at once."

        client = _get_client(ctx)

        results = []
        errors = []
        for sid in station_ids:
            try:
                columns, records = await client.get_observations(sid, hours=1)
                if records:
                    latest = records[0]
                    obs: dict[str, Any] = {"station": sid.upper()}
                    dt = latest.get("datetime")
                    obs["time"] = dt.strftime("%m-%d %H:%M") if dt else "---"
                    for col in (
                        "WSPD",
                        "GST",
                        "WDIR",
                        "WVHT",
                        "DPD",
                        "PRES",
                        "ATMP",
                        "WTMP",
                    ):
                        val = latest.get(col)
                        obs[col] = val
                    results.append(obs)
                else:
                    errors.append(f"{sid.upper()}: No recent data")
            except Exception as e:
                errors.append(f"{sid.upper()}: {type(e).__name__}")

        if response_format == "json":
            return json.dumps({"comparisons": results, "errors": errors}, indent=2)

        lines = ["## Station Comparison"]
        lines.append("")

        # Build comparison table
        comp_cols = ["WSPD", "GST", "WVHT", "DPD", "PRES", "ATMP", "WTMP"]
        col_labels = [COLUMN_LABELS.get(c, c) for c in comp_cols]

        lines.append("| Station | Time | " + " | ".join(col_labels) + " |")
        lines.append("| --- | --- | " + " | ".join("---" for _ in comp_cols) + " |")

        for r in results:
            cells = [r["station"], r["time"]]
            for col in comp_cols:
                val = r.get(col)
                if val is None:
                    cells.append("---")
                elif isinstance(val, float):
                    cells.append(f"{val:.1f}")
                else:
                    cells.append(str(val))
            lines.append("| " + " | ".join(cells) + " |")

        if errors:
            lines.append("")
            lines.append("**Errors:**")
            for err in errors:
                lines.append(f"- {err}")

        lines.append("")
        lines.append(
            f"*{len(results)} stations compared. Data from NOAA NDBC realtime2.*"
        )

        return "\n".join(lines)
    except Exception as e:
        return handle_ndbc_error(e)
