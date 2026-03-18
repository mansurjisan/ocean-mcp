"""Tools for checking NOS OFS data availability."""

import os
from datetime import datetime

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..config_reader import ConfigReader
from ..server import mcp


def _get_reader(ctx: Context) -> ConfigReader:
    return ctx.request_context.lifespan_context["config_reader"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def nos_check_forcing(
    ctx: Context,
    system_name: str,
    date: str | None = None,
    cycle: str = "12",
) -> str:
    """Check if forcing input data is available for an OFS run.

    Checks common WCOSS2/HPC paths for GFS, HRRR, RTOFS, and NWM data.
    Helps diagnose prep failures caused by missing upstream data.

    Args:
        system_name: OFS system name (e.g. 'secofs', 'stofs_3d_atl').
        date: Date to check in YYYYMMDD format. Defaults to today.
        cycle: Cycle hour (e.g. '00', '06', '12', '18'). Default '12'.
    """
    reader = _get_reader(ctx)

    try:
        config = reader.get_config(system_name)
    except Exception as e:
        return f"Error: {e}"

    if not date:
        date = datetime.now().strftime("%Y%m%d")

    # Extract forcing sources from config
    forcing = config.get("forcing", {})
    atm = forcing.get("atmospheric", {})
    ocean = forcing.get("ocean", {})
    river = forcing.get("river", {})

    checks: list[dict] = []

    # Common WCOSS2/HPC data paths
    com_base = os.environ.get("COMROOT", "/lfs/h1/ops/prod/com")
    dcom_base = os.environ.get("DCOMROOT", "/lfs/h1/ops/prod/dcom")  # noqa: F841

    # GFS check
    if atm.get("primary", "").upper() == "GFS":
        gfs_paths = [
            f"{com_base}/gfs/v16.3/gfs.{date}/{cycle}/atmos/"
            f"gfs.t{cycle}z.pgrb2.0p25.f000",
            f"/scratch5/purged/{os.environ.get('USER', '')}/com/"
            f"gfs.{date}/gfs.t{cycle}z.pgrb2.0p25.f000",
        ]
        found = any(os.path.exists(p) for p in gfs_paths)
        checks.append(
            {
                "source": "GFS",
                "status": "available" if found else "not found",
                "paths_checked": gfs_paths,
            }
        )

    # HRRR check
    if (
        atm.get("secondary", "").upper() == "HRRR"
        or atm.get("forecast_source2", "").upper() == "HRRR"
    ):
        hrrr_paths = [
            f"{com_base}/hrrr/v4.1/hrrr.{date}/conus/hrrr.t{cycle}z.wrfprsf00.grib2",
        ]
        found = any(os.path.exists(p) for p in hrrr_paths)
        checks.append(
            {
                "source": "HRRR",
                "status": "available" if found else "not found",
                "paths_checked": hrrr_paths,
            }
        )

    # RTOFS check
    if ocean.get("primary", "").upper() == "RTOFS" or ocean.get("enabled"):
        rtofs_paths = [
            f"{com_base}/rtofs/v2.3/rtofs.{date}/rtofs_glo_3dz_f024_daily_3ztio.nc",
        ]
        found = any(os.path.exists(p) for p in rtofs_paths)
        checks.append(
            {
                "source": "RTOFS",
                "status": "available" if found else "not found",
                "paths_checked": rtofs_paths,
            }
        )

    # NWM (river) check
    if river.get("primary", "").lower() == "nwm":
        nwm_paths = [
            f"{com_base}/nwm/v3.0/nwm.{date}/medium_range_mem1/"
            f"nwm.t{cycle}z.medium_range.channel_rt_1.f001.conus.nc",
        ]
        found = any(os.path.exists(p) for p in nwm_paths)
        checks.append(
            {
                "source": "NWM",
                "status": "available" if found else "not found",
                "paths_checked": nwm_paths,
            }
        )

    # Build report
    lines = [f"## Forcing Availability: {system_name} ({date} {cycle}z)\n"]

    all_ok = all(c["status"] == "available" for c in checks)
    lines.append(f"**Overall**: {'ALL AVAILABLE' if all_ok else 'SOME MISSING'}\n")

    for check in checks:
        icon = "\u2713" if check["status"] == "available" else "\u2717"
        lines.append(f"- **{check['source']}**: {icon} {check['status']}")

    if not all_ok:
        lines.append("\n### Missing Data Paths")
        for check in checks:
            if check["status"] != "available":
                for p in check["paths_checked"]:
                    lines.append(f"- `{p}`")

    return "\n".join(lines)
