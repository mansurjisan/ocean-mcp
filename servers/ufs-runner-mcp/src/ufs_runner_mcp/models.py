"""Constants, enums, and validation for UFS Runner."""

from __future__ import annotations

import logging
import os
import re
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


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
    """Return allowed path prefixes, including any from UFS_RUNNER_ALLOWED_PATHS.

    A configured entry that resolves down to just the filesystem root (e.g.
    a literal "/", or a relative value whose parent chain bottoms out there)
    would match *every* absolute path via the symlink-transparent containment
    check in _prefix_matches — silently disabling the sandbox instead of
    adding a narrower allowance. That's essentially never the intent (no
    admin means to allow the whole filesystem by setting this), so such an
    entry is dropped with a loud warning rather than silently honored or
    silently ignored.
    """
    extra = os.environ.get("UFS_RUNNER_ALLOWED_PATHS", "")
    prefixes = list(_ALLOWED_PATH_PREFIXES)
    if extra.strip():
        for raw in extra.split(":"):
            candidate = raw.strip()
            if not candidate:
                continue
            resolved_candidate = Path(candidate).resolve()
            if len(resolved_candidate.parts) < 2:
                logger.warning(
                    "UFS_RUNNER_ALLOWED_PATHS entry %r resolves to the "
                    "filesystem root (%s); ignoring it instead of allowing "
                    "every path. Configure a specific subdirectory instead.",
                    candidate,
                    resolved_candidate,
                )
                continue
            prefixes.append(candidate)
    return prefixes


def _prefix_matches(resolved: Path, prefix: str) -> bool:
    """Check whether *resolved* falls under *prefix*.

    Two independent checks are tried; either is sufficient:

    1. Numbered-mount leniency, on the RAW (unresolved) prefix. Real RDHPCS
       mounts are numbered (/scratch3, /scratch4, /work2/noaa, ...), so a
       plain is_relative_to(prefix) check (or the raw-string-prefix check it
       replaced) rejects every genuine mount except the exact, un-numbered
       name. Only the path *component immediately after the filesystem root*
       is given digit-suffix leniency — e.g. prefix "/scratch" matches
       resolved component "scratch5" — via re.fullmatch on that single
       component, so "work-attacker" / "workshop" / "scratchpad-evil" still
       fail (they are not the base name plus only digits). Any deeper
       components of the prefix (e.g. the "noaa" in a hypothetical
       "/work/noaa") must still match exactly, same as the original
       is_relative_to check.

       This is deliberately checked on the prefix's raw string components,
       not resolved ones: numbered siblings (e.g. /work2) are separate
       mounts, not reachable through whatever symlink /work itself might be
       on a given site, so resolving the prefix first would compare against
       the symlink's *target* name instead of "work" and silently break this
       leniency.

    2. Symlink-transparent containment, on the RESOLVED prefix. Many real
       HPC sites symlink an allowed root itself (e.g. /work -> /lustre/work,
       /scratch -> /gpfs/scratch, or a custom env-configured prefix pointing
       at a symlink). The input path is already resolved by the caller, so
       also resolve the prefix and check plain containment in that resolved
       space — the same principle as the original pre-numbered-mount code
       (is_relative_to), which resolved both sides. This also transparently
       handles a *relative* env-supplied prefix, since Path.resolve() anchors
       it against the current working directory instead of leaving it as a
       silent no-op. A prefix that resolves to just the filesystem root is
       never treated as a match here (see get_allowed_prefixes).
    """
    resolved_parts = resolved.parts

    # 1. numbered-mount leniency, compared on the raw prefix
    raw_prefix_parts = Path(prefix).parts
    if len(raw_prefix_parts) >= 2 and len(resolved_parts) >= 2:
        base_name = raw_prefix_parts[1]
        pattern = re.compile(rf"^{re.escape(base_name)}\d*$")
        if pattern.fullmatch(resolved_parts[1]):
            remaining_prefix_parts = raw_prefix_parts[2:]
            candidate = resolved_parts[2 : 2 + len(remaining_prefix_parts)]
            if not remaining_prefix_parts or list(candidate) == list(
                remaining_prefix_parts
            ):
                return True

    # 2. symlink-transparent containment, compared on the resolved prefix
    resolved_prefix_parts = Path(prefix).resolve().parts
    if len(resolved_prefix_parts) >= 2 and len(resolved_parts) >= len(
        resolved_prefix_parts
    ):
        if resolved_parts[: len(resolved_prefix_parts)] == resolved_prefix_parts:
            return True

    return False


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
