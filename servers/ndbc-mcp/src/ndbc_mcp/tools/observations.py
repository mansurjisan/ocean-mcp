"""Observation retrieval tools for NDBC buoy data."""

import json
from datetime import datetime, timezone
from typing import Any, Literal

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import NDBCClient, handle_ndbc_error
from ..models import COLUMN_DESCRIPTIONS, COLUMN_LABELS, degrees_to_compass
from ..server import mcp


def _get_client(ctx: Context) -> NDBCClient:
    return ctx.request_context.lifespan_context["ndbc_client"]


def _format_value(val: Any, col: str) -> str:
    """Format a single observation value for display."""
    if val is None:
        return "---"
    if isinstance(val, float):
        if col in ("WDIR", "MWD"):
            return f"{int(val)}"
        if col in ("PRES",):
            return f"{val:.1f}"
        return f"{val:.1f}"
    return str(val)


def _capped_obs_json(
    station_id: str,
    hours: int,
    records: list[dict],
    build_row,
    max_records: int,
) -> str:
    """Serialize NDBC records to JSON, capped to the most recent max_records.

    NDBC realtime2 returns observations newest-first, so the head is the most
    recent — keep records[:max_records]. A long window (hours up to 1080) is
    thousands of ~10-minute records; dumping them all floods the model's
    context. The wrapper carries truncated/returned/total (and a hint when
    trimmed) so the caller knows the series was cut and how to narrow it.
    """
    total = len(records)
    truncated = total > max_records
    kept = records[:max_records] if truncated else records
    out: dict[str, Any] = {
        "station": station_id.upper(),
        "hours": hours,
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "truncated": truncated,
        "returned": len(kept),
        "total": total,
        "records": [build_row(r) for r in kept],
    }
    if truncated:
        out["hint"] = (
            f"Showing the most recent {len(kept)} of {total} records. "
            "Lower `hours` to narrow the series."
        )
    return json.dumps(out, indent=2)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ndbc_get_latest_observation(
    ctx: Context,
    station_id: str,
    response_format: Literal["markdown", "json"] = "markdown",
) -> str:
    """Get the latest observation from an NDBC station.

    Returns all available variables (wind, waves, temperature, pressure, etc.)
    as key-value pairs.

    Args:
        station_id: NDBC station ID (e.g., '41001', '46042', 'TPLM2').
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        columns, records = await client.get_observations(station_id)

        if not records:
            return f"No recent observations found for station {station_id.upper()}."

        latest = records[0]  # Most recent record

        if response_format == "json":
            out = {"station": station_id.upper(), "observation": {}}
            for col in columns[5:]:  # Skip datetime columns
                val = latest.get(col)
                if val is not None:
                    out["observation"][col] = val
            if latest.get("datetime"):
                out["observation"]["datetime"] = latest["datetime"].isoformat()
            return json.dumps(out, indent=2)

        dt = latest.get("datetime")
        time_str = dt.strftime("%Y-%m-%d %H:%M UTC") if dt else "Unknown"

        lines = [f"## Latest Observation \u2014 {station_id.upper()}"]
        lines.append(f"**Time**: {time_str}")
        lines.append("")

        for col in columns[5:]:  # Skip YY MM DD hh mm
            val = latest.get(col)
            if val is None:
                continue
            label = COLUMN_LABELS.get(col, col)
            formatted = _format_value(val, col)
            if col in ("WDIR", "MWD"):
                compass = degrees_to_compass(val)
                formatted = f"{formatted}\u00b0 ({compass})"
            lines.append(f"**{label}**: {formatted}")

        lines.append("")
        lines.append(f"*Data from NOAA NDBC realtime2. Station {station_id.upper()}.*")

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
async def ndbc_get_observations(
    ctx: Context,
    station_id: str,
    hours: int = 24,
    variables: list[str] | None = None,
    response_format: Literal["markdown", "json"] = "markdown",
    max_records: int = 2000,
) -> str:
    """Get time series observations from an NDBC station.

    Data covers the last 45 days (rolling), updated every ~10 minutes.

    Args:
        station_id: NDBC station ID (e.g., '41001', '46042').
        hours: Number of hours to retrieve (default 24, max 1080 = 45 days).
        variables: Optional list of variables to include (e.g., ['WSPD', 'WVHT', 'WTMP']). Default: all available.
        response_format: Output format — 'markdown' (default) or 'json'.
        max_records: Cap on JSON records returned (default 2000). A long hours
            window is thousands of points; only the most recent max_records are
            kept, and the JSON flags any truncation. (Markdown is already capped.)
    """
    try:
        if hours < 1 or hours > 1080:
            return "Validation Error: hours must be between 1 and 1080 (45 days)."

        client = _get_client(ctx)
        columns, records = await client.get_observations(station_id, hours=hours)

        if not records:
            return f"No observations found for station {station_id.upper()} in the past {hours} hours."

        # Filter columns if variables specified
        data_cols = columns[5:]  # Skip datetime columns
        if variables:
            valid_vars = [v.upper() for v in variables if v.upper() in data_cols]
            if not valid_vars:
                avail = ", ".join(data_cols)
                return f"None of the requested variables found. Available: {avail}"
            data_cols = valid_vars

        if response_format == "json":

            def _row(r: dict) -> dict[str, Any]:
                row: dict[str, Any] = {}
                if r.get("datetime"):
                    row["datetime"] = r["datetime"].isoformat()
                for col in data_cols:
                    row[col] = r.get(col)
                return row

            return _capped_obs_json(station_id, hours, records, _row, max_records)

        # Markdown table
        display_cols = data_cols[:8]  # Cap columns for readability

        lines = [f"## Observations \u2014 {station_id.upper()} (past {hours}h)"]
        lines.append(f"**Records**: {len(records)}")
        lines.append("")

        header_labels = ["Time"] + [COLUMN_LABELS.get(c, c) for c in display_cols]
        lines.append("| " + " | ".join(header_labels) + " |")
        lines.append("| " + " | ".join("---" for _ in header_labels) + " |")

        for r in records[:200]:  # Cap display rows
            dt = r.get("datetime")
            time_str = dt.strftime("%m-%d %H:%M") if dt else "---"
            cells = [time_str]
            for col in display_cols:
                cells.append(_format_value(r.get(col), col))
            lines.append("| " + " | ".join(cells) + " |")

        if len(records) > 200:
            lines.append(f"\n*Showing first 200 of {len(records)} records.*")

        lines.append("")
        extra_cols = data_cols[8:]
        if extra_cols:
            lines.append(f"*Additional variables available: {', '.join(extra_cols)}*")
        lines.append("*Data from NOAA NDBC realtime2.*")

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
async def ndbc_get_wave_summary(
    ctx: Context,
    station_id: str,
    hours: int = 24,
    response_format: Literal["markdown", "json"] = "markdown",
    max_records: int = 2000,
) -> str:
    """Get spectral wave summary from an NDBC station.

    Provides swell and wind-wave separation from the .spec file.

    Args:
        station_id: NDBC station ID (e.g., '41001', '46042').
        hours: Number of hours to retrieve (default 24, max 1080).
        response_format: Output format — 'markdown' (default) or 'json'.
        max_records: Cap on JSON records returned (default 2000). Only the most
            recent max_records are kept, and the JSON flags any truncation.
            (Markdown is already capped.)
    """
    try:
        if hours < 1 or hours > 1080:
            return "Validation Error: hours must be between 1 and 1080 (45 days)."

        client = _get_client(ctx)
        columns, records = await client.get_observations(
            station_id, hours=hours, extension="spec"
        )

        if not records:
            return f"No spectral wave data found for station {station_id.upper()} in the past {hours} hours. Not all stations have spectral data."

        if response_format == "json":

            def _row(r: dict) -> dict[str, Any]:
                row: dict[str, Any] = {}
                if r.get("datetime"):
                    row["datetime"] = r["datetime"].isoformat()
                for col in columns[5:]:
                    row[col] = r.get(col)
                return row

            return _capped_obs_json(station_id, hours, records, _row, max_records)

        data_cols = columns[5:]
        display_cols = data_cols[:8]

        lines = [
            f"## Wave Spectral Summary \u2014 {station_id.upper()} (past {hours}h)"
        ]
        lines.append(f"**Records**: {len(records)}")
        lines.append("")

        header_labels = ["Time"] + [COLUMN_LABELS.get(c, c) for c in display_cols]
        lines.append("| " + " | ".join(header_labels) + " |")
        lines.append("| " + " | ".join("---" for _ in header_labels) + " |")

        for r in records[:100]:
            dt = r.get("datetime")
            time_str = dt.strftime("%m-%d %H:%M") if dt else "---"
            cells = [time_str]
            for col in display_cols:
                cells.append(_format_value(r.get(col), col))
            lines.append("| " + " | ".join(cells) + " |")

        if len(records) > 100:
            lines.append(f"\n*Showing first 100 of {len(records)} records.*")

        lines.append("")

        # Column descriptions
        lines.append("### Variable Descriptions")
        for col in display_cols:
            desc = COLUMN_DESCRIPTIONS.get(col, col)
            lines.append(f"- **{col}**: {desc}")

        lines.append("")
        lines.append("*Data from NOAA NDBC realtime2 spectral files.*")

        return "\n".join(lines)
    except Exception as e:
        return handle_ndbc_error(e)
