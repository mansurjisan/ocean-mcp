"""Reads NOS OFS YAML configurations and ecFlow suite definitions."""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml


class ConfigError(Exception):
    """Raised when a configuration operation fails."""


# Known OFS systems and their metadata
_OFS_SYSTEMS = {
    "stofs_3d_atl": {"model": "SCHISM", "framework": "stofs", "region": "Atlantic"},
    "stofs_3d_pac": {"model": "SCHISM", "framework": "stofs", "region": "Pacific"},
    "stofs_2d_glo": {"model": "ADCIRC", "framework": "stofs", "region": "Global"},
    "stofs_2d_atl": {"model": "ADCIRC", "framework": "stofs", "region": "Atlantic"},
    "secofs": {"model": "SCHISM", "framework": "comf", "region": "Southeast Coast"},
    "secofs_ufs": {
        "model": "SCHISM (UFS)",
        "framework": "comf",
        "region": "Southeast Coast",
    },
    "creofs": {
        "model": "SCHISM",
        "framework": "comf",
        "region": "Columbia River Estuary",
    },
    "cbofs": {"model": "ROMS", "framework": "comf", "region": "Chesapeake Bay"},
    "dbofs": {"model": "ROMS", "framework": "comf", "region": "Delaware Bay"},
    "leofs": {"model": "FVCOM", "framework": "comf", "region": "Lake Erie"},
    "ngofs2": {
        "model": "FVCOM",
        "framework": "comf",
        "region": "Northern Gulf of Mexico",
    },
}


class ConfigReader:
    """Reads NOS OFS configuration files from the nos-workflow repository."""

    def __init__(self, workflow_dir: str | None = None):
        self.workflow_dir = Path(
            workflow_dir
            or os.environ.get("NOS_WORKFLOW_DIR", "")
            or self._find_workflow_dir()
        )

    def _find_workflow_dir(self) -> str:
        """Try to auto-detect the nos-workflow directory."""
        user = os.environ.get("USER", "")
        candidates = [
            Path(f"/scratch5/purged/{user}/nos-workflow"),
            Path(f"/scratch/{user}/nos-workflow"),
            Path.home() / "nos-workflow",
            Path("/tmp/nos-workflow"),
        ]
        for c in candidates:
            if (c / "parm" / "systems").is_dir():
                return str(c)
        return ""

    def _config_dir(self) -> Path:
        """Return the systems config directory."""
        d = self.workflow_dir / "parm" / "systems"
        if not d.is_dir():
            raise ConfigError(
                f"Config directory not found: {d}. "
                f"Set NOS_WORKFLOW_DIR to the nos-workflow repo path."
            )
        return d

    def _base_config_dir(self) -> Path:
        return self.workflow_dir / "parm" / "base"

    def _ecf_dir(self) -> Path:
        return self.workflow_dir / "ecf"

    def list_systems(self) -> list[dict]:
        """List all available OFS systems."""
        try:
            config_dir = self._config_dir()
        except ConfigError:
            # Fall back to hardcoded list if dir not found
            return [
                {"name": name, **meta} for name, meta in sorted(_OFS_SYSTEMS.items())
            ]

        systems = []
        for yaml_file in sorted(config_dir.glob("*.yaml")):
            name = yaml_file.stem
            meta = _OFS_SYSTEMS.get(
                name, {"model": "unknown", "framework": "unknown", "region": "unknown"}
            )
            systems.append({"name": name, "config_file": str(yaml_file), **meta})
        return systems

    def get_config(self, system_name: str) -> dict:
        """Read and return the full YAML config for an OFS system."""
        config_dir = self._config_dir()
        config_file = config_dir / f"{system_name}.yaml"
        if not config_file.exists():
            available = [f.stem for f in config_dir.glob("*.yaml")]
            raise ConfigError(
                f"Config '{system_name}' not found. Available: {', '.join(available)}"
            )

        with open(config_file) as f:
            config = yaml.safe_load(f) or {}

        # Load base config if referenced
        base_name = config.get("_base")
        if base_name:
            base_file = self._base_config_dir() / f"{base_name}.yaml"
            if base_file.exists():
                with open(base_file) as f:
                    base = yaml.safe_load(f) or {}
                config["_base_config"] = base

        return config

    def get_config_section(
        self, system_name: str, section: str
    ) -> dict | list | str | None:
        """Get a specific section from the config (e.g. 'forcing', 'model.physics')."""
        config = self.get_config(system_name)
        parts = section.split(".")
        current = config
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    def compare_configs(
        self, system_a: str, system_b: str, sections: list[str] | None = None
    ) -> dict:
        """Compare two OFS system configs, highlighting differences."""
        config_a = self.get_config(system_a)
        config_b = self.get_config(system_b)

        # Default comparison sections
        if not sections:
            sections = ["grid", "forcing", "model", "resources", "output"]

        differences: dict[str, dict] = {}
        for section in sections:
            val_a = _deep_get(config_a, section)
            val_b = _deep_get(config_b, section)
            if val_a != val_b:
                differences[section] = {
                    system_a: val_a,
                    system_b: val_b,
                }

        return {
            "system_a": system_a,
            "system_b": system_b,
            "sections_compared": sections,
            "differences": differences,
            "identical_sections": [s for s in sections if s not in differences],
        }

    def get_ecflow_suite(self, system_name: str | None = None) -> str:
        """Read the ecFlow suite definition."""
        ecf_dir = self._ecf_dir()
        def_file = ecf_dir / "def" / "nosofs.def"
        if not def_file.exists():
            raise ConfigError(f"ecFlow definition not found: {def_file}")

        content = def_file.read_text()

        # If system requested, extract just that family
        if system_name:
            return _extract_ecflow_family(content, system_name)

        return content

    def get_ensemble_config(self, system_name: str) -> dict | None:
        """Get ensemble configuration for a system."""
        config = self.get_config(system_name)
        ensemble = config.get("ensemble")
        if not ensemble:
            return None
        return ensemble

    def get_domain_bounds(self, system_name: str) -> dict | None:
        """Get the geographic domain bounds for an OFS system.

        Returns dict with lon_min, lon_max, lat_min, lat_max or None.
        """
        config = self.get_config(system_name)
        grid = config.get("grid", {})
        domain = grid.get("domain", {})
        if all(k in domain for k in ("lon_min", "lon_max", "lat_min", "lat_max")):
            return {
                "lon_min": domain["lon_min"],
                "lon_max": domain["lon_max"],
                "lat_min": domain["lat_min"],
                "lat_max": domain["lat_max"],
            }
        return None

    def diagnose_log(self, log_content: str) -> dict:
        """Parse a job log or fatal.error and classify the failure."""
        lowered = log_content.lower()
        diagnosis = {
            "error_type": "unknown",
            "error_message": "",
            "suggestion": "",
        }

        # SCHISM-specific errors
        if "h_c needs to be larger" in log_content:
            match = re.search(r"h_c needs to be larger:\s*([\d.]+)", log_content)
            h_c_val = match.group(1) if match else "unknown"
            diagnosis.update(
                {
                    "error_type": "SCHISM vertical coordinate",
                    "error_message": f"h_c ({h_c_val}) is too small for the domain bathymetry. "
                    "The hybrid S/Z vertical coordinate requires h_c to be larger than "
                    "the minimum depth in the hgrid.",
                    "suggestion": "Increase h_c in vgrid.in or check hgrid.gr3 for shallow nodes. "
                    "Common fix: set h_c to at least max(depth_at_boundary_nodes) + buffer.",
                }
            )
        elif "cfl" in lowered or "courant" in lowered:
            diagnosis.update(
                {
                    "error_type": "CFL violation",
                    "error_message": "Time step is too large for the grid resolution and flow speed.",
                    "suggestion": "Reduce dt in param.nml (CORE section). "
                    "For SCHISM: try halving dt. Check for very small elements near the coast.",
                }
            )
        elif "mpi_abort" in lowered or "mpi error" in lowered:
            diagnosis.update(
                {
                    "error_type": "MPI failure",
                    "error_message": "MPI communication error — a rank crashed or timed out.",
                    "suggestion": "Check for memory issues (OOM), file I/O errors, or "
                    "NaN propagation. Review rank 0 stderr for the root cause.",
                }
            )
        elif "killed" in lowered or "oom" in lowered or "out of memory" in lowered:
            diagnosis.update(
                {
                    "error_type": "Out of memory",
                    "error_message": "Job exceeded memory allocation.",
                    "suggestion": "Increase --mem or --mem-per-cpu in sbatch. "
                    "Or reduce domain size / increase number of MPI ranks.",
                }
            )
        elif "timeout" in lowered or "walltime" in lowered or "time limit" in lowered:
            diagnosis.update(
                {
                    "error_type": "Wall time exceeded",
                    "error_message": "Job ran out of wall clock time.",
                    "suggestion": "Increase --time in sbatch or reduce forecast length.",
                }
            )
        elif "file not found" in lowered or "no such file" in lowered:
            match = re.search(
                r"(?:file not found|no such file)[:\s]*([^\n]+)",
                log_content,
                re.IGNORECASE,
            )
            missing = match.group(1).strip() if match else "unknown"
            diagnosis.update(
                {
                    "error_type": "Missing file",
                    "error_message": f"Required input file not found: {missing}",
                    "suggestion": "Check that the prep stage completed successfully "
                    "and all forcing/boundary files are staged.",
                }
            )
        elif "nan" in lowered and ("blowup" in lowered or "instab" in lowered):
            diagnosis.update(
                {
                    "error_type": "Numerical instability",
                    "error_message": "NaN values detected — model blew up.",
                    "suggestion": "Reduce time step, check boundary conditions for "
                    "discontinuities, verify forcing data quality.",
                }
            )
        elif "abort" in lowered:
            # Generic abort
            lines = log_content.strip().split("\n")
            abort_line = next(
                (line for line in lines if "abort" in line.lower()),
                lines[-1] if lines else "",
            )
            diagnosis.update(
                {
                    "error_type": "Model abort",
                    "error_message": abort_line.strip(),
                    "suggestion": "Check the full log for the root cause above the ABORT line.",
                }
            )

        return diagnosis


def _deep_get(d: dict, key: str):
    """Get a nested value using dot notation."""
    parts = key.split(".")
    current = d
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _extract_ecflow_family(content: str, family_name: str) -> str:
    """Extract an ecFlow family block from the suite definition."""
    lines = content.split("\n")
    result = []
    depth = 0
    in_family = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"family {family_name}"):
            in_family = True
            depth = 1
            result.append(line)
            continue

        if in_family:
            if stripped.startswith("family "):
                depth += 1
            elif stripped.startswith("endfamily"):
                depth -= 1
                if depth == 0:
                    result.append(line)
                    in_family = False
                    continue
            result.append(line)

    if not result:
        return f"No ecFlow family found for '{family_name}' in the suite definition."
    return "\n".join(result)
