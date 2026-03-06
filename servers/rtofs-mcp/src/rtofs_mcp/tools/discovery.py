"""Tools: rtofs_get_system_info, rtofs_list_datasets, rtofs_get_latest_time."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import RTOFSClient
from ..models import DATASETS, RTOFS_SPECS, THREDDS_BASE
from ..server import mcp


def _get_client(ctx: Context) -> RTOFSClient:
    return ctx.request_context.lifespan_context["rtofs_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def rtofs_get_system_info(
    ctx: Context,
    response_format: str = "markdown",
) -> str:
    """Get RTOFS system overview — model specifications, variables, resolution, and coverage.

    Returns metadata about the Real-Time Ocean Forecast System (RTOFS/ESPC)
    including model resolution, forecast length, available variables, and data
    source information. No network request needed.

    Args:
        response_format: 'markdown' (default) or 'json'.
    """
    if response_format == "json":
        return json.dumps(
            {
                "system": RTOFS_SPECS,
                "datasets": {
                    k: {"description": v["description"], "dimensions": v["dimensions"]}
                    for k, v in DATASETS.items()
                },
                "thredds_base": THREDDS_BASE,
            },
            indent=2,
        )

    lines = ["# RTOFS System Information"]
    lines.append("")
    lines.append(
        "> **RTOFS** (Real-Time Ocean Forecast System) is NOAA's global 1/12° "
        "ocean forecast based on HYCOM, providing SST, salinity, currents, and "
        "sea surface height forecasts out to 8 days. Data is served via the "
        "HYCOM THREDDS Data Server."
    )
    lines.append("")

    lines.append("## Model Specifications")
    for key, val in RTOFS_SPECS.items():
        label = key.replace("_", " ").title()
        lines.append(f"- **{label}**: {val}")

    lines.append("")
    lines.append("## Available Datasets")
    lines.append("")
    lines.append("| Dataset | Dimensions | Description |")
    lines.append("| --- | --- | --- |")
    for key, ds in DATASETS.items():
        lines.append(f"| {key} | {ds['dimensions']} | {ds['description']} |")

    lines.append("")
    lines.append("## Variables")
    lines.append("- **SSH** (surf_el): Sea Surface Height (m)")
    lines.append("- **Temperature** (water_temp): Water Temperature at all depths (°C)")
    lines.append("- **Salinity** (salinity): Salinity at all depths (PSU)")
    lines.append(
        "- **Currents** (water_u, water_v): Ocean current velocities at all depths (m/s)"
    )

    lines.append("")
    lines.append(f"*Data from HYCOM THREDDS: {THREDDS_BASE}*")
    return "\n".join(lines)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def rtofs_list_datasets(
    ctx: Context,
    check_availability: bool = True,
    response_format: str = "markdown",
) -> str:
    """List RTOFS datasets on HYCOM THREDDS with optional availability check.

    Shows the 4 RTOFS/ESPC datasets (SSH, temperature, salinity, currents)
    and optionally checks if each is currently accessible.

    Args:
        check_availability: If True, ping each dataset to check live status. Default: True.
        response_format: 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)

        results = []
        for key, ds in DATASETS.items():
            var_list = list(ds["variables"].keys())
            entry = {
                "key": key,
                "description": ds["description"],
                "dimensions": ds["dimensions"],
                "variables": var_list,
                "status": "unknown",
            }

            if check_availability:
                available = await client.check_dataset_available(key)
                entry["status"] = "available" if available else "unavailable"

            results.append(entry)

        if response_format == "json":
            return json.dumps({"datasets": results}, indent=2)

        lines = ["## RTOFS Datasets on HYCOM THREDDS"]
        lines.append("")

        lines.append("| Dataset | Dims | Variables | Status |")
        lines.append("| --- | --- | --- | --- |")

        for r in results:
            status = r["status"].capitalize() if check_availability else "—"
            lines.append(
                f"| {r['key']} | {r['dimensions']} | "
                f"{', '.join(r['variables'])} | {status} |"
            )

        lines.append("")
        lines.append(f"*Source: HYCOM THREDDS ({THREDDS_BASE})*")
        return "\n".join(lines)

    except Exception as e:
        from ..client import handle_rtofs_error

        return handle_rtofs_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def rtofs_get_latest_time(
    ctx: Context,
    dataset: str = "ssh",
    response_format: str = "markdown",
) -> str:
    """Query the latest available forecast time from HYCOM THREDDS.

    Useful for determining what forecast data is currently available before
    making data queries.

    Args:
        dataset: One of 'ssh', 'sst', 'sss', 'currents'. Default: 'ssh'.
        response_format: 'markdown' (default) or 'json'.
    """
    try:
        if dataset not in DATASETS:
            valid = ", ".join(DATASETS.keys())
            return f"Unknown dataset '{dataset}'. Valid options: {valid}"

        client = _get_client(ctx)
        time_range = await client.get_dataset_time_range(dataset)

        if time_range is None:
            return (
                f"Could not retrieve time range for dataset '{dataset}'. "
                "HYCOM THREDDS may be temporarily unavailable."
            )

        if response_format == "json":
            return json.dumps(
                {
                    "dataset": dataset,
                    "first_time": time_range["first"],
                    "last_time": time_range["last"],
                },
                indent=2,
            )

        lines = [
            f"## RTOFS Time Range — {dataset}",
            f"**Dataset**: {DATASETS[dataset]['description']}",
            f"**First available**: {time_range['first']}",
            f"**Last available**: {time_range['last']}",
            "",
            "*Source: HYCOM THREDDS*",
        ]
        return "\n".join(lines)

    except Exception as e:
        from ..client import handle_rtofs_error

        return handle_rtofs_error(e)
