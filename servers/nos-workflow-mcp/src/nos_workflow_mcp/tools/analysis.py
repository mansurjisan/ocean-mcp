"""Tools for forecast anomaly detection and model skill assessment."""

import json
import os
import re

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..server import mcp

# ── Climatological baselines for common variables ────────────────────────

_CLIMATOLOGY: dict[str, dict[str, float]] = {
    "zeta": {"mean": 0.0, "std": 1.0, "abs_max": 5.0},
    "elev": {"mean": 0.0, "std": 1.0, "abs_max": 5.0},
    "ssh": {"mean": 0.0, "std": 1.0, "abs_max": 5.0},
    "water_level": {"mean": 0.0, "std": 1.0, "abs_max": 5.0},
    "temp": {"mean": 15.0, "std": 10.0, "hard_min": -5.0, "hard_max": 45.0},
    "temperature": {"mean": 15.0, "std": 10.0, "hard_min": -5.0, "hard_max": 45.0},
    "salt": {"mean": 32.0, "std": 5.0, "hard_min": 0.0, "hard_max": 42.0},
    "salinity": {"mean": 32.0, "std": 5.0, "hard_min": 0.0, "hard_max": 42.0},
}


def _classify_sigma(sigma: float) -> str:
    """Classify a sigma value into NORMAL / WARNING / ANOMALY."""
    if sigma > 3.0:
        return "ANOMALY"
    if sigma > 2.0:
        return "WARNING"
    return "NORMAL"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def nos_anomaly_check(
    ctx: Context,
    file_path: str,
    variable: str = "zeta",
    baseline_mean: float | None = None,
    baseline_std: float | None = None,
) -> str:
    """Check if a model forecast output has anomalous values.

    Compares the current forecast statistics against a provided baseline
    (mean and standard deviation). If no baseline is provided, uses
    built-in climatological ranges for common variables.

    Flags anomalies when values exceed mean +/- 3*std.

    Args:
        file_path: Path to the NetCDF forecast file.
        variable: Variable to check (default 'zeta' for water level).
        baseline_mean: Expected mean value (from historical runs).
        baseline_std: Expected standard deviation.
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

    if variable not in ds.data_vars:
        available = ", ".join(sorted(ds.data_vars))
        ds.close()
        return (
            f"Error: Variable '{variable}' not found in dataset.\n"
            f"Available variables: {available}"
        )

    var_data = ds[variable]
    if not np.issubdtype(var_data.dtype, np.number):
        ds.close()
        return f"Error: Variable '{variable}' is not numeric (dtype={var_data.dtype})."

    values = var_data.values
    cur_min = float(np.nanmin(values))
    cur_max = float(np.nanmax(values))
    cur_mean = float(np.nanmean(values))
    cur_std = float(np.nanstd(values))
    total = values.size
    nan_count = (
        int(np.isnan(values).sum()) if np.issubdtype(var_data.dtype, np.floating) else 0
    )

    ds.close()

    # Determine baseline
    if baseline_mean is not None and baseline_std is not None:
        bl_mean = baseline_mean
        bl_std = baseline_std
        baseline_source = "user-provided"
    elif variable in _CLIMATOLOGY:
        clim = _CLIMATOLOGY[variable]
        bl_mean = clim["mean"]
        bl_std = clim["std"]
        baseline_source = "built-in climatology"
    else:
        # No baseline available -- report stats only
        lines = [
            f"## Anomaly Check: {os.path.basename(file_path)}",
            f"**Variable**: `{variable}`\n",
            "**Status**: UNKNOWN (no baseline available)\n",
            "No user-provided baseline and no built-in climatology for "
            f"`{variable}`. Reporting raw statistics only.\n",
            "### Current Statistics",
            f"- Min: {cur_min:.6g}",
            f"- Max: {cur_max:.6g}",
            f"- Mean: {cur_mean:.6g}",
            f"- Std: {cur_std:.6g}",
            f"- Points: {total} ({nan_count} NaN)",
        ]
        return "\n".join(lines)

    # Compute sigma deviations
    if bl_std > 0:
        sigma_mean = abs(cur_mean - bl_mean) / bl_std
        sigma_max = abs(cur_max - bl_mean) / bl_std
        sigma_min = abs(cur_min - bl_mean) / bl_std
    else:
        sigma_mean = 0.0 if cur_mean == bl_mean else float("inf")
        sigma_max = 0.0 if cur_max == bl_mean else float("inf")
        sigma_min = 0.0 if cur_min == bl_mean else float("inf")

    worst_sigma = max(sigma_mean, sigma_max, sigma_min)
    status = _classify_sigma(worst_sigma)

    # Also check hard limits from climatology
    clim_entry = _CLIMATOLOGY.get(variable, {})
    hard_flags: list[str] = []
    if "abs_max" in clim_entry:
        limit = clim_entry["abs_max"]
        if cur_max > limit or cur_min < -limit:
            hard_flags.append(
                f"Values outside absolute range [-{limit}, {limit}]: "
                f"min={cur_min:.4g}, max={cur_max:.4g}"
            )
            status = "ANOMALY"
    if "hard_max" in clim_entry and cur_max > clim_entry["hard_max"]:
        hard_flags.append(
            f"Max value {cur_max:.4g} exceeds hard limit {clim_entry['hard_max']}"
        )
        status = "ANOMALY"
    if "hard_min" in clim_entry and cur_min < clim_entry["hard_min"]:
        hard_flags.append(
            f"Min value {cur_min:.4g} below hard limit {clim_entry['hard_min']}"
        )
        status = "ANOMALY"

    # Build report
    lines = [
        f"## Anomaly Check: {os.path.basename(file_path)}",
        f"**Variable**: `{variable}`",
        f"**Baseline**: {baseline_source} (mean={bl_mean:.4g}, std={bl_std:.4g})\n",
        f"**Status**: {status}\n",
        "### Current Statistics",
        f"- Min: {cur_min:.6g}",
        f"- Max: {cur_max:.6g}",
        f"- Mean: {cur_mean:.6g}",
        f"- Std: {cur_std:.6g}",
        f"- Points: {total} ({nan_count} NaN)\n",
        "### Sigma Deviations",
        f"- Mean deviation: {sigma_mean:.2f} sigma",
        f"- Max deviation: {sigma_max:.2f} sigma",
        f"- Min deviation: {sigma_min:.2f} sigma",
    ]

    if hard_flags:
        lines.append("\n### Hard Limit Violations")
        for flag in hard_flags:
            lines.append(f"- {flag}")

    return "\n".join(lines)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def nos_skill_assessment(
    ctx: Context,
    model_file: str,
    model_variable: str,
    obs_file: str | None = None,
    obs_variable: str | None = None,
    obs_values: str | None = None,
) -> str:
    """Compute skill assessment metrics between model output and observations.

    Computes RMSE, bias (mean error), correlation coefficient, and
    Willmott skill score. Can compare against an observations NetCDF
    file or against directly provided observation values.

    Args:
        model_file: Path to the model output NetCDF file.
        model_variable: Variable name in the model file.
        obs_file: Path to observations NetCDF file (optional).
        obs_variable: Variable name in observations file.
        obs_values: JSON string of observation values as alternative
            to obs_file (e.g. '[0.5, 0.6, 0.4, 0.7]').
    """
    # Validate paths
    for path_arg in (model_file, obs_file):
        if path_arg is not None and re.search(r"[;&|`$(){}]", path_arg):
            return f"Error: Unsafe characters in path: '{path_arg}'"

    if obs_file is None and obs_values is None:
        return (
            "Error: Must provide either obs_file or obs_values. "
            "Cannot compute skill metrics without observations."
        )

    if not os.path.isfile(model_file):
        return f"Error: Model file not found: {model_file}"

    try:
        import numpy as np
        import xarray as xr
    except ImportError:
        return (
            "Error: xarray/numpy not available. "
            "Install with: pip install xarray netCDF4 numpy"
        )

    # ── Load model data ──────────────────────────────────────────────
    try:
        model_ds = xr.open_dataset(model_file)
    except Exception as e:
        return f"Error opening model file: {e}"

    if model_variable not in model_ds.data_vars:
        available = ", ".join(sorted(model_ds.data_vars))
        model_ds.close()
        return (
            f"Error: Variable '{model_variable}' not found in model file.\n"
            f"Available variables: {available}"
        )

    model_data = model_ds[model_variable].values.flatten()
    model_ds.close()

    # ── Load observation data ────────────────────────────────────────
    if obs_values is not None:
        try:
            parsed = json.loads(obs_values)
            if not isinstance(parsed, list):
                return "Error: obs_values must be a JSON array (e.g. '[0.5, 0.6]')."
            obs_data = np.array(parsed, dtype=np.float64)
        except (json.JSONDecodeError, ValueError) as e:
            return f"Error parsing obs_values JSON: {e}"
    else:
        # obs_file path
        if not os.path.isfile(obs_file):
            return f"Error: Observations file not found: {obs_file}"
        ov = obs_variable if obs_variable else model_variable
        try:
            obs_ds = xr.open_dataset(obs_file)
        except Exception as e:
            return f"Error opening observations file: {e}"

        if ov not in obs_ds.data_vars:
            available = ", ".join(sorted(obs_ds.data_vars))
            obs_ds.close()
            return (
                f"Error: Variable '{ov}' not found in observations file.\n"
                f"Available variables: {available}"
            )
        obs_data = obs_ds[ov].values.flatten()
        obs_ds.close()

    # ── Remove NaN from both arrays ──────────────────────────────────
    model_flat = model_data.astype(np.float64)
    obs_flat = obs_data.astype(np.float64)

    # Align lengths -- use the shorter series
    n = min(len(model_flat), len(obs_flat))
    if n == 0:
        return "Error: No data points available for comparison."
    model_flat = model_flat[:n]
    obs_flat = obs_flat[:n]

    # Remove positions where either has NaN
    valid_mask = ~(np.isnan(model_flat) | np.isnan(obs_flat))
    model_valid = model_flat[valid_mask]
    obs_valid = obs_flat[valid_mask]
    n_valid = len(model_valid)

    if n_valid < 2:
        return (
            "Error: Fewer than 2 valid (non-NaN) paired data points. "
            "Cannot compute meaningful skill metrics."
        )

    # ── Compute metrics ──────────────────────────────────────────────
    diff = model_valid - obs_valid
    bias = float(np.mean(diff))
    rmse = float(np.sqrt(np.mean(diff**2)))
    mae = float(np.mean(np.abs(diff)))

    # Correlation coefficient
    if np.std(model_valid) == 0 or np.std(obs_valid) == 0:
        correlation = float("nan")
    else:
        correlation = float(np.corrcoef(model_valid, obs_valid)[0, 1])

    # Willmott skill score (d)
    obs_mean = np.mean(obs_valid)
    numerator = np.sum(diff**2)
    denominator = np.sum(
        (np.abs(model_valid - obs_mean) + np.abs(obs_valid - obs_mean)) ** 2
    )
    willmott_d = (
        float(1.0 - numerator / denominator) if denominator > 0 else float("nan")
    )

    # ── Build report ─────────────────────────────────────────────────
    lines = [
        f"## Skill Assessment: {os.path.basename(model_file)}",
        f"**Model variable**: `{model_variable}`",
    ]
    if obs_file:
        lines.append(f"**Observations**: `{os.path.basename(obs_file)}`")
    else:
        lines.append(f"**Observations**: inline values ({len(obs_data)} points)")
    lines.append(f"**Paired points**: {n_valid} (of {n} aligned)\n")

    lines.append("### Metrics\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| RMSE | {rmse:.6g} |")
    lines.append(f"| Bias (mean error) | {bias:.6g} |")
    lines.append(f"| MAE | {mae:.6g} |")
    lines.append(f"| Correlation (r) | {correlation:.6g} |")
    lines.append(f"| Willmott d | {willmott_d:.6g} |")

    lines.append("\n### Interpretation\n")
    # Qualitative assessment
    if abs(bias) < rmse * 0.1:
        lines.append("- **Bias**: Negligible — model is well-centered on observations.")
    elif bias > 0:
        lines.append(f"- **Bias**: Model over-predicts by {bias:.4g} on average.")
    else:
        lines.append(f"- **Bias**: Model under-predicts by {abs(bias):.4g} on average.")

    if not np.isnan(correlation):
        if correlation > 0.9:
            lines.append(f"- **Correlation**: Excellent ({correlation:.4f}).")
        elif correlation > 0.7:
            lines.append(f"- **Correlation**: Good ({correlation:.4f}).")
        elif correlation > 0.5:
            lines.append(f"- **Correlation**: Moderate ({correlation:.4f}).")
        else:
            lines.append(f"- **Correlation**: Weak ({correlation:.4f}).")

    if not np.isnan(willmott_d):
        if willmott_d > 0.9:
            lines.append(f"- **Willmott d**: Excellent agreement ({willmott_d:.4f}).")
        elif willmott_d > 0.7:
            lines.append(f"- **Willmott d**: Good agreement ({willmott_d:.4f}).")
        elif willmott_d > 0.5:
            lines.append(f"- **Willmott d**: Moderate agreement ({willmott_d:.4f}).")
        else:
            lines.append(f"- **Willmott d**: Poor agreement ({willmott_d:.4f}).")

    return "\n".join(lines)
