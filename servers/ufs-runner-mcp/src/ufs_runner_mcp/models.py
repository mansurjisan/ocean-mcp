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


def validate_run_dir(run_dir: str) -> str | None:
    """Validate that run_dir is under an allowed path prefix.

    Returns None if valid, or an error message if not.
    """
    resolved = str(Path(run_dir).resolve())
    prefixes = get_allowed_prefixes()
    for prefix in prefixes:
        if resolved.startswith(prefix):
            return None
    allowed = ", ".join(prefixes)
    return (
        f"Rejected: run_dir '{run_dir}' is not under an allowed path. "
        f"Allowed prefixes: {allowed}"
    )


def validate_job_id(job_id: str) -> str | None:
    """Validate a Slurm job ID. Returns None if valid, error message if not."""
    if not re.match(r"^\d+$", job_id):
        return f"Invalid job ID: '{job_id}'. Must be numeric."
    return None


# Default Slurm resource limits to prevent runaway requests
MAX_NODES = int(os.environ.get("UFS_RUNNER_MAX_NODES", "50"))
MAX_WALL_HOURS = int(os.environ.get("UFS_RUNNER_MAX_WALL_HOURS", "12"))
