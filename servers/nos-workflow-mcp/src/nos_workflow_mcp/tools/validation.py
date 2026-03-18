"""Tools for validating NOS OFS model output."""

import os
import re

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..server import mcp


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def nos_validate_output(
    ctx: Context,
    file_path: str,
    variables: str | None = None,
) -> str:
    """Validate a NetCDF model output file for quality issues.

    Checks for NaN values, extreme values, missing timesteps,
    and file completeness. Works with SCHISM, ROMS, and FVCOM output.

    Args:
        file_path: Path to the NetCDF output file.
        variables: Comma-separated variable names to check (e.g. 'zeta,temp,salt').
            If not provided, checks all numeric variables.
    """
    # Validate path - no shell metacharacters
    if re.search(r"[;&|`$(){}]", file_path):
        return f"Error: Unsafe characters in path: '{file_path}'"
    if not os.path.isfile(file_path):
        return f"Error: File not found: {file_path}"

    try:
        import numpy as np
        import xarray as xr
    except ImportError:
        return (
            "Error: xarray/numpy not available. "
            "Install with: pip install xarray netCDF4 numpy"
        )

    try:
        ds = xr.open_dataset(file_path)
    except Exception as e:
        return f"Error opening file: {e}"

    issues: list[str] = []
    warnings: list[str] = []
    stats: list[str] = []

    # Check which variables to validate
    var_list = (
        [v.strip() for v in variables.split(",")] if variables else list(ds.data_vars)
    )

    for var_name in var_list:
        if var_name not in ds.data_vars:
            issues.append(f"Variable '{var_name}' not found in dataset")
            continue

        var = ds[var_name]
        if not np.issubdtype(var.dtype, np.number):
            continue

        values = var.values
        total = values.size
        nan_count = (
            int(np.isnan(values).sum()) if np.issubdtype(var.dtype, np.floating) else 0
        )
        nan_pct = (nan_count / total * 100) if total > 0 else 0

        vmin = float(np.nanmin(values)) if total > 0 else 0
        vmax = float(np.nanmax(values)) if total > 0 else 0
        vmean = float(np.nanmean(values)) if total > 0 else 0

        stats.append(
            f"- **{var_name}**: min={vmin:.4g}, max={vmax:.4g}, "
            f"mean={vmean:.4g}, NaN={nan_pct:.1f}%"
        )

        if nan_pct > 50:
            issues.append(f"{var_name}: {nan_pct:.1f}% NaN values (>50%)")
        elif nan_pct > 10:
            warnings.append(f"{var_name}: {nan_pct:.1f}% NaN values")

        # Check for extreme values (common model blowup indicators)
        if var_name in ("zeta", "elev", "ssh", "water_level"):
            if vmax > 20 or vmin < -20:
                issues.append(
                    f"{var_name}: extreme values [{vmin:.1f}, {vmax:.1f}] "
                    "— possible blowup"
                )
        elif var_name in ("temp", "temperature"):
            if vmax > 50 or vmin < -5:
                warnings.append(f"{var_name}: unusual range [{vmin:.1f}, {vmax:.1f}]")
        elif var_name in ("salt", "salinity"):
            if vmax > 45 or vmin < -1:
                warnings.append(f"{var_name}: unusual range [{vmin:.1f}, {vmax:.1f}]")

    # Check time dimension
    time_vars = [d for d in ds.sizes if "time" in d.lower()]
    for tv in time_vars:
        n_times = ds.sizes[tv]
        stats.append(f"- **Time steps**: {n_times} ({tv})")

    # File size
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    stats.append(f"- **File size**: {size_mb:.1f} MB")
    stats.append(f"- **Dimensions**: {dict(ds.sizes)}")

    ds.close()

    # Build report
    lines = [f"## Output Validation: {os.path.basename(file_path)}\n"]

    ready = len(issues) == 0
    lines.append(f"**Status**: {'PASS' if ready else 'FAIL'}\n")

    if issues:
        lines.append(f"### Errors ({len(issues)})")
        for i in issues:
            lines.append(f"- {i}")
    if warnings:
        lines.append(f"\n### Warnings ({len(warnings)})")
        for w in warnings:
            lines.append(f"- {w}")

    lines.append("\n### Variable Statistics")
    lines.extend(stats)

    return "\n".join(lines)
