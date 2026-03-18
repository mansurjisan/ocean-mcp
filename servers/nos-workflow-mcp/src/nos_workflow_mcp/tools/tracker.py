"""Tools for tracking NOS OFS config changes and parameter dependencies."""

import re
import subprocess

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..config_reader import ConfigReader
from ..server import mcp


def _get_reader(ctx: Context) -> ConfigReader:
    return ctx.request_context.lifespan_context["config_reader"]


# Safety: only allow alphanumeric, dot, dash, underscore, tilde, slash, caret
_SAFE_REF_RE = re.compile(r"^[A-Za-z0-9._/~^-]+$")


def _validate_ref(ref: str) -> str | None:
    """Return an error message if the git ref contains unsafe characters."""
    if not _SAFE_REF_RE.match(ref):
        return f"Unsafe characters in git ref: '{ref}'"
    return None


# ── Dependency knowledge base ────────────────────────────────────────────

_DEPENDENCY_MAP: dict[str, dict] = {
    "dt": {
        "display_name": "time step (dt)",
        "affected_parameters": [
            {
                "name": "CFL stability",
                "relationship": "CFL number is proportional to dt / dx. Reducing grid "
                "resolution (dx) or increasing flow speed requires a smaller dt.",
            },
            {
                "name": "EXTSTEP_SECONDS",
                "relationship": "External mode time step must divide evenly into dt. "
                "Typically EXTSTEP_SECONDS = dt / ISPLIT.",
            },
            {
                "name": "NHIS (history output interval)",
                "relationship": "NHIS should be a multiple of dt to align output with "
                "model time steps.",
            },
            {
                "name": "NSTA (station output interval)",
                "relationship": "NSTA should be a multiple of dt to align station "
                "output with model time steps.",
            },
            {
                "name": "NRST (restart output interval)",
                "relationship": "NRST should be a multiple of dt for consistent "
                "restart checkpoints.",
            },
        ],
    },
    "nprocs": {
        "display_name": "processor count (nprocs)",
        "affected_parameters": [
            {
                "name": "TOTAL_TASKS",
                "relationship": "TOTAL_TASKS in the Slurm job must match nprocs.",
            },
            {
                "name": "partition / node count",
                "relationship": "Number of nodes = ceil(nprocs / tasks_per_node). "
                "May require a different Slurm partition if node count changes.",
            },
            {
                "name": "memory requirements",
                "relationship": "Total memory scales with nprocs. Each rank holds a "
                "domain partition, so fewer ranks means more memory per rank.",
            },
        ],
    },
    "grid": {
        "display_name": "grid configuration",
        "affected_parameters": [
            {
                "name": "all forcing interpolation",
                "relationship": "Atmospheric, ocean, and river forcing must be "
                "re-interpolated to any new grid geometry.",
            },
            {
                "name": "boundary conditions",
                "relationship": "Open boundary node lists and forcing files are "
                "grid-specific and must be regenerated.",
            },
            {
                "name": "output station coverage",
                "relationship": "Station extraction points must fall within the new "
                "grid domain. Stations outside the domain will produce missing values.",
            },
        ],
    },
    "forcing": {
        "display_name": "forcing source configuration",
        "affected_parameters": [
            {
                "name": "MET_NUM",
                "relationship": "MET_NUM selects the atmospheric forcing provider. "
                "Changing the source (e.g., GFS to HRRR) requires updating MET_NUM.",
            },
            {
                "name": "available variables",
                "relationship": "Different forcing sources provide different variable "
                "sets (e.g., HRRR includes sub-hourly fields that GFS does not).",
            },
            {
                "name": "time resolution",
                "relationship": "Forcing time step varies by source (e.g., GFS 3-hourly "
                "vs HRRR hourly). The model interpolation must match.",
            },
        ],
    },
}


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def nos_config_diff(
    ctx: Context,
    system_name: str,
    ref_a: str = "HEAD",
    ref_b: str = "HEAD~1",
) -> str:
    """Compare a system YAML config between two git refs (tags, branches, commits).

    Uses the nos-workflow git repository to show what changed in the config
    file between two points in history.

    Args:
        system_name: OFS system name (e.g. 'secofs', 'stofs_3d_atl').
        ref_a: First git ref — tag, branch, or commit (default 'HEAD').
        ref_b: Second git ref (default 'HEAD~1').
    """
    reader = _get_reader(ctx)
    workflow_dir = str(reader.workflow_dir)

    if not workflow_dir:
        return "Error: NOS_WORKFLOW_DIR is not set and could not be auto-detected."

    # Validate refs
    for ref in (ref_a, ref_b):
        err = _validate_ref(ref)
        if err:
            return f"Error: {err}"

    config_path = f"parm/systems/{system_name}.yaml"

    try:
        result = subprocess.run(
            ["git", "-C", workflow_dir, "diff", ref_a, ref_b, "--", config_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return "Error: git is not available on this system."
    except subprocess.TimeoutExpired:
        return "Error: git diff timed out."

    if result.returncode != 0:
        stderr = result.stderr.strip()
        return f"Error running git diff: {stderr}"

    diff_output = result.stdout.strip()
    if not diff_output:
        return f"No changes to `{config_path}` between `{ref_a}` and `{ref_b}`."

    return (
        f"## Config Diff: {system_name}\n"
        f"**Comparing** `{ref_a}` vs `{ref_b}`\n\n"
        f"```diff\n{diff_output}\n```"
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def nos_dependency_analysis(
    ctx: Context,
    system_name: str,
    parameter_path: str,
) -> str:
    """Analyze which other parameters are affected when a config value changes.

    Given a parameter path (e.g. 'model.physics.dt'), returns the downstream
    effects and relationships based on NOS OFS domain knowledge.

    Args:
        system_name: OFS system name for context (e.g. 'secofs').
        parameter_path: Dot-separated parameter path (e.g. 'model.physics.dt',
            'resources.nprocs', 'grid', 'forcing').
    """
    # Extract the leaf parameter name for lookup
    parts = parameter_path.split(".")
    leaf = parts[-1]

    entry = _DEPENDENCY_MAP.get(leaf)
    if entry is None:
        known = ", ".join(sorted(_DEPENDENCY_MAP.keys()))
        return (
            f"No dependency information available for parameter `{parameter_path}`.\n\n"
            f"Known parameters with dependency data: {known}.\n\n"
            f"If this is a model-specific parameter, consult the model documentation "
            f"or namelist reference for {system_name}."
        )

    lines = [
        f"## Dependency Analysis: {system_name}",
        f"**Parameter**: `{parameter_path}` ({entry['display_name']})\n",
        f"### Affected Parameters ({len(entry['affected_parameters'])})\n",
    ]

    for i, dep in enumerate(entry["affected_parameters"], 1):
        lines.append(f"**{i}. {dep['name']}**")
        lines.append(f"   {dep['relationship']}\n")

    return "\n".join(lines)
