"""Constants, enums, and validation for UFS Runner."""

from __future__ import annotations

import os
import re
from enum import Enum
from pathlib import Path


class ModelType(str, Enum):
    """Supported UFS-Coastal model configurations."""

    SCHISM = "schism"
    ADCIRC = "adcirc"
    FVCOM = "fvcom"


# Safety: only allow experiments under scratch directories
_ALLOWED_PATH_PREFIXES = [
    "/scratch",
    "/work",
    "/contrib",
]


def get_allowed_prefixes() -> list[str]:
    """Return allowed path prefixes, including any from UFS_RUNNER_ALLOWED_PATHS."""
    extra = os.environ.get("UFS_RUNNER_ALLOWED_PATHS", "")
    prefixes = list(_ALLOWED_PATH_PREFIXES)
    if extra.strip():
        prefixes.extend(p.strip() for p in extra.split(":") if p.strip())
    return prefixes


def _prefix_matches(resolved: Path, prefix: str) -> bool:
    """Check whether *resolved* falls under *prefix*.

    Real RDHPCS mounts are numbered (/scratch3, /scratch4, /work2/noaa, ...),
    so a plain is_relative_to(prefix) check (or the raw-string-prefix check
    it replaced) rejects every genuine mount except the exact, un-numbered
    name. Only the path *component immediately after the filesystem root* is
    given digit-suffix leniency — e.g. prefix "/scratch" matches resolved
    component "scratch5" — via re.fullmatch on that single component, so
    "work-attacker" / "workshop" / "scratchpad-evil" still fail (they are not
    the base name plus only digits). Any deeper components of the prefix
    (e.g. the "noaa" in a hypothetical "/work/noaa") must still match
    exactly, same as the original is_relative_to check.
    """
    prefix_parts = Path(prefix).parts
    resolved_parts = resolved.parts
    if len(prefix_parts) < 2 or len(resolved_parts) < 2:
        return False
    base_name = prefix_parts[1]
    pattern = re.compile(rf"^{re.escape(base_name)}\d*$")
    if not pattern.fullmatch(resolved_parts[1]):
        return False
    remaining_prefix_parts = prefix_parts[2:]
    if not remaining_prefix_parts:
        return True
    candidate = resolved_parts[2 : 2 + len(remaining_prefix_parts)]
    return list(candidate) == list(remaining_prefix_parts)


def validate_path(path: str, label: str = "path") -> str | None:
    """Validate that *path* is under an allowed path prefix.

    Returns None if valid, or an error message if not.
    """
    # Compare on path-component boundaries, not raw string prefix:
    # str.startswith("/work") wrongly accepted "/work-attacker", "/workshop",
    # "/scratchpad-evil" — a full sandbox escape. _prefix_matches (like
    # is_relative_to, which it replaces) only accepts genuine descendants,
    # while still tolerating numbered HPC mounts (see its docstring).
    resolved = Path(path).resolve()
    prefixes = get_allowed_prefixes()
    for prefix in prefixes:
        if _prefix_matches(resolved, prefix):
            return None
    allowed = ", ".join(prefixes)
    return (
        f"Rejected: {label} '{path}' is not under an allowed path. "
        f"Allowed prefixes: {allowed}"
    )


def validate_run_dir(run_dir: str) -> str | None:
    """Validate that run_dir is under an allowed path prefix."""
    return validate_path(run_dir, label="run_dir")


def validate_job_id(job_id: str) -> str | None:
    """Validate a Slurm job ID. Returns None if valid, error message if not."""
    if not re.match(r"^\d+$", job_id):
        return f"Invalid job ID: '{job_id}'. Must be numeric."
    return None


# Pattern for values that are safe to interpolate into shell scripts.
# Allows word chars, dots, slashes, hyphens — no shell metacharacters.
_SAFE_SHELL_RE = re.compile(r"^[\w./-]+$")

# Template variable names that end up in shell command contexts
_SHELL_CONTEXT_VARS = {
    "output_dir",
    "restart_dir",
    "job_name",
    "total_tasks",
    "nodes",
    "tasks_per_node",
    "wall_minutes",
}


def validate_template_variables(variables: dict) -> str | None:
    """Check that variables used in shell contexts are safe.

    Returns None if all OK, or an error message describing the problem.
    """
    for key in _SHELL_CONTEXT_VARS:
        if key not in variables:
            continue
        val = str(variables[key])
        if not _SAFE_SHELL_RE.match(val):
            return (
                f"Unsafe value for template variable '{key}': '{val}'. "
                f"Only word characters, dots, slashes, and hyphens are allowed."
            )
    return None


def validate_shell_safe_values(variables: dict, keys) -> str | None:
    """Reject user-supplied override values containing shell metacharacters.

    _render_template substitutes every flat override into all text files,
    including run_*.sh / *.slurm, so ANY user-controlled value can reach a
    shell context — not only the fixed _SHELL_CONTEXT_VARS names. The
    allowlist in validate_template_variables is therefore insufficient on its
    own; every user override value must also match the safe pattern.

    Returns None if all OK, or an error message describing the problem.
    """
    for key in keys:
        if key not in variables:
            continue
        val = str(variables[key])
        if not _SAFE_SHELL_RE.match(val):
            return (
                f"Unsafe value for override '{key}': '{val}'. "
                f"Only word characters, dots, slashes, and hyphens are allowed "
                f"(no spaces or shell metacharacters)."
            )
    return None


# Default Slurm resource limits to prevent runaway requests
MAX_NODES = int(os.environ.get("UFS_RUNNER_MAX_NODES", "50"))
MAX_WALL_HOURS = int(os.environ.get("UFS_RUNNER_MAX_WALL_HOURS", "12"))
