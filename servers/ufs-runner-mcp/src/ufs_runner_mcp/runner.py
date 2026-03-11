"""Core UFS experiment runner — directory setup, validation, submission."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import f90nml
import yaml

from .models import (
    MAX_NODES,
    MAX_WALL_HOURS,
    ModelType,
    validate_job_id,
    validate_run_dir,
)


def _load_template_defaults(template_path: Path) -> dict:
    """Load defaults.yaml from a template directory."""
    defaults_file = template_path / "defaults.yaml"
    if not defaults_file.exists():
        return {}
    with open(defaults_file) as f:
        return yaml.safe_load(f) or {}


def _compute_derived_vars(variables: dict) -> dict:
    """Compute derived variables from base variables."""
    v = dict(variables)
    # Computed fields for ufs.configure petlist_bounds
    atm = int(v.get("atm_tasks", 160))
    ocn = int(v.get("ocn_tasks", 160))
    v["atm_tasks_minus1"] = atm - 1
    v["total_tasks_minus1"] = atm + ocn - 1
    v["total_tasks"] = atm + ocn
    v["atm_tasks"] = atm
    v["ocn_tasks"] = ocn
    return v


def _render_template(content: str, variables: dict) -> str:
    """Replace {{var}} placeholders with values from variables dict."""

    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        if key in variables:
            return str(variables[key])
        return match.group(0)  # Leave unresolved placeholders as-is

    return re.sub(r"\{\{(\w+)\}\}", replacer, content)


def _load_template_defaults(template_path: Path) -> dict:
    """Load defaults.yaml from a template directory."""
    defaults_file = template_path / "defaults.yaml"
    if not defaults_file.exists():
        return {}
    with open(defaults_file) as f:
        return yaml.safe_load(f) or {}


def _compute_derived_vars(variables: dict) -> dict:
    """Compute derived variables from base variables."""
    v = dict(variables)
    # Computed fields for ufs.configure petlist_bounds
    atm = int(v.get("atm_tasks", 160))
    ocn = int(v.get("ocn_tasks", 160))
    v["atm_tasks_minus1"] = atm - 1
    v["total_tasks_minus1"] = atm + ocn - 1
    v["total_tasks"] = atm + ocn
    v["atm_tasks"] = atm
    v["ocn_tasks"] = ocn
    return v


def _render_template(content: str, variables: dict) -> str:
    """Replace {{var}} placeholders with values from variables dict."""
    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        if key in variables:
            return str(variables[key])
        return match.group(0)  # Leave unresolved placeholders as-is
    return re.sub(r"\{\{(\w+)\}\}", replacer, content)


class RunnerError(Exception):
    """Raised when a runner operation fails."""


class UfsRunner:
    """Manages UFS-Coastal experiment lifecycle."""

    def __init__(self) -> None:
        self._templates_dir = Path(__file__).parent / "templates"

    # ------------------------------------------------------------------
    # 1. Create experiment
    # ------------------------------------------------------------------

    def create_experiment(
        self,
        model_type: str,
        run_dir: str,
        template: str | None = None,
        overrides: dict | None = None,
        input_data_dir: str | None = None,
    ) -> dict:
        """Set up a UFS experiment directory from a template.

        Returns a summary dict with paths and status.
        """
        # Validate model type
        try:
            model = ModelType(model_type.lower())
        except ValueError:
            valid = ", ".join(m.value for m in ModelType)
            raise RunnerError(f"Unknown model_type '{model_type}'. Supported: {valid}")

        # Validate run directory
        err = validate_run_dir(run_dir)
        if err:
            raise RunnerError(err)

        run_path = Path(run_dir)
        if run_path.exists() and any(run_path.iterdir()):
            raise RunnerError(
                f"Run directory '{run_dir}' already exists and is not empty. "
                f"Choose a different path or remove it first."
            )

        # Find template — try explicit name, then model_default, then first match
        template_name = template or self._find_default_template(model.value)
        template_path = self._templates_dir / template_name
        if not template_path.is_dir():
            available = (
                [
                    d.name
                    for d in self._templates_dir.iterdir()
                    if d.is_dir() and not d.name.startswith(".")
                ]
                if self._templates_dir.exists()
                else []
            )
            raise RunnerError(
                f"Template '{template_name}' not found. "
                f"Available: {', '.join(available) or 'none'}"
            )

        # Load template defaults and merge with user overrides
        variables = _load_template_defaults(template_path)
        if overrides:
            # Flat keys override defaults directly
            for key, value in overrides.items():
                if isinstance(value, dict):
                    # Nested dict = namelist group override (applied later via f90nml)
                    continue
                variables[key] = value
        variables = _compute_derived_vars(variables)

        # Copy template to run directory, rendering {{var}} placeholders
        run_path.mkdir(parents=True, exist_ok=True)
        _skip_files = {"defaults.yaml", "TEMPLATE_README"}
        for item in template_path.iterdir():
            if item.name in _skip_files:
                continue
            dest = run_path / item.name
            if item.is_dir():
                shutil.copytree(item, dest)
            elif item.suffix in (".nc", ".gr3", ".ll", ".exe", ".sif"):
                # Binary files: copy without rendering
                shutil.copy2(item, dest)
            else:
                # Text files: render template variables
                content = item.read_text()
                rendered = _render_template(content, variables)
                dest.write_text(rendered)

        # Apply f90nml namelist overrides (for nested dict overrides)
        if overrides:
            nml_overrides = {k: v for k, v in overrides.items() if isinstance(v, dict)}
            if nml_overrides:
                self._apply_overrides(run_path, nml_overrides)

        # Stage input data from user's input directory
        staged_files: list[str] = []
        if input_data_dir:
            staged_files = self._stage_input_data(
                input_dir=Path(input_data_dir),
                run_path=run_path,
                model_type=model.value,
            )

        # Write metadata
        meta = {
            "model_type": model.value,
            "template": template_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": os.environ.get("USER", "unknown"),
            "overrides_applied": overrides or {},
            "resolved_variables": {
                k: v for k, v in variables.items() if not isinstance(v, (dict, list))
            },
            "input_data_dir": input_data_dir,
            "staged_files": staged_files,
            "status": "created",
        }
        (run_path / ".ufs_experiment.json").write_text(json.dumps(meta, indent=2))

        return {
            "status": "created",
            "run_dir": str(run_path),
            "model_type": model.value,
            "template": template_name,
            "files": sorted(
                str(f.relative_to(run_path)) for f in run_path.rglob("*") if f.is_file()
            ),
            "staged_files": staged_files,
        }

    def _find_default_template(self, model_value: str) -> str:
        """Find the best matching template for a model type."""
        if not self._templates_dir.exists():
            return f"{model_value}_default"
        # Look for exact default first, then any template starting with model name
        default_name = f"{model_value}_default"
        if (self._templates_dir / default_name).is_dir():
            return default_name
        for d in sorted(self._templates_dir.iterdir()):
            if d.is_dir() and d.name.startswith(model_value):
                return d.name
        return default_name  # Will fail later with clear error

    def _apply_overrides(self, run_path: Path, overrides: dict) -> None:
        """Apply namelist overrides using f90nml."""
        # Look for param.nml (SCHISM) or fort.15 (ADCIRC) or model_configure
        nml_files = list(run_path.glob("*.nml")) + list(
            run_path.glob("model_configure")
        )
        for nml_file in nml_files:
            try:
                nml = f90nml.read(str(nml_file))
                for group, params in overrides.items():
                    if group in nml:
                        for key, value in params.items():
                            nml[group][key] = value
                nml.write(str(nml_file), force=True)
            except Exception:
                continue  # Skip files that aren't valid namelists

    # ------------------------------------------------------------------
    # 2. Validate experiment
    # ------------------------------------------------------------------

    def validate_experiment(self, run_dir: str) -> dict:
        """Check that an experiment directory is ready to submit."""
        err = validate_run_dir(run_dir)
        if err:
            raise RunnerError(err)

        run_path = Path(run_dir)
        if not run_path.is_dir():
            raise RunnerError(f"Run directory '{run_dir}' does not exist.")

        issues: list[dict] = []
        warnings: list[str] = []

        # Check metadata
        meta_file = run_path / ".ufs_experiment.json"
        if not meta_file.exists():
            issues.append(
                {
                    "severity": "error",
                    "message": "Missing .ufs_experiment.json metadata",
                }
            )
            model_type = "unknown"
        else:
            meta = json.loads(meta_file.read_text())
            model_type = meta.get("model_type", "unknown")

        # Check for required files based on model type
        required_files = self._get_required_files(model_type)
        for fname in required_files:
            if not (run_path / fname).exists():
                issues.append(
                    {"severity": "error", "message": f"Missing required file: {fname}"}
                )

        # Check for Slurm script
        slurm_scripts = list(run_path.glob("*.slurm")) + list(run_path.glob("run_*.sh"))
        if not slurm_scripts:
            warnings.append("No Slurm submission script found (*.slurm or run_*.sh)")

        # Check namelists parse correctly
        for nml_file in run_path.glob("*.nml"):
            try:
                f90nml.read(str(nml_file))
            except Exception as e:
                issues.append(
                    {
                        "severity": "error",
                        "message": f"Invalid namelist {nml_file.name}: {e}",
                    }
                )

        return {
            "run_dir": str(run_path),
            "model_type": model_type,
            "errors": [i for i in issues if i["severity"] == "error"],
            "warnings": warnings,
            "ready": len([i for i in issues if i["severity"] == "error"]) == 0,
            "files_found": sorted(
                str(f.relative_to(run_path)) for f in run_path.rglob("*") if f.is_file()
            ),
        }

    def _get_required_files(self, model_type: str) -> list[str]:
        """Return required files for a given model type."""
        common = ["model_configure", "ufs.configure"]
        model_specific = {
            "schism": [
                "param.nml",
                "hgrid.gr3",
                "hgrid.ll",
                "vgrid.in",
                "rough.gr3",
                "bctides.in",
                "datm_in",
                "datm.streams",
            ],
            "adcirc": [
                "fort.14",
                "fort.15",
                "fort.13",
                "datm_in",
                "datm.streams",
            ],
            "fvcom": ["namelist.input", "datm_in", "datm.streams"],
        }
        return common + model_specific.get(model_type, [])

    # ------------------------------------------------------------------
    # 3. Submit experiment
    # ------------------------------------------------------------------

    def submit_experiment(
        self,
        run_dir: str,
        account: str,
        partition: str,
        nodes: int = 1,
        wall_hours: int = 1,
        qos: str | None = None,
        dry_run: bool = True,
    ) -> dict:
        """Submit a UFS experiment via sbatch.

        By default runs in dry_run mode — shows the command without executing.
        Set dry_run=False to actually submit.
        """
        err = validate_run_dir(run_dir)
        if err:
            raise RunnerError(err)

        run_path = Path(run_dir)
        if not run_path.is_dir():
            raise RunnerError(f"Run directory '{run_dir}' does not exist.")

        # Safety limits
        if nodes > MAX_NODES:
            raise RunnerError(f"Requested {nodes} nodes exceeds limit of {MAX_NODES}.")
        if wall_hours > MAX_WALL_HOURS:
            raise RunnerError(
                f"Requested {wall_hours}h wall time exceeds limit of {MAX_WALL_HOURS}h."
            )

        # Validate account/partition format
        if not re.match(r"^[\w-]+$", account):
            raise RunnerError(f"Invalid account name: '{account}'")
        if not re.match(r"^[\w-]+$", partition):
            raise RunnerError(f"Invalid partition name: '{partition}'")

        # Find the run script
        run_scripts = list(run_path.glob("run_*.sh")) + list(run_path.glob("*.slurm"))
        if not run_scripts:
            raise RunnerError(
                f"No submission script found in '{run_dir}'. "
                f"Expected run_*.sh or *.slurm"
            )
        script = run_scripts[0]

        # Build sbatch command
        cmd = [
            "sbatch",
            f"--account={account}",
            f"--partition={partition}",
            f"--nodes={nodes}",
            f"--time={wall_hours:02d}:00:00",
            f"--chdir={run_dir}",
        ]
        if qos:
            if not re.match(r"^[\w-]+$", qos):
                raise RunnerError(f"Invalid QOS: '{qos}'")
            cmd.append(f"--qos={qos}")
        cmd.append(str(script))

        if dry_run:
            # Update metadata
            self._update_meta(run_path, {"status": "dry_run_ready"})
            return {
                "mode": "dry_run",
                "command": " ".join(cmd),
                "run_dir": str(run_path),
                "script": str(script.name),
                "message": "Dry run — review the command above. "
                "Call submit_ufs_experiment again with dry_run=false to submit.",
            }

        # Actually submit
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            raise RunnerError(
                "sbatch not found. Are you on a Slurm login/service node?"
            )
        except subprocess.TimeoutExpired:
            raise RunnerError("sbatch timed out after 30s.")

        if result.returncode != 0:
            raise RunnerError(f"sbatch failed: {result.stderr.strip()}")

        # Parse job ID from "Submitted batch job 12345"
        match = re.search(r"Submitted batch job (\d+)", result.stdout)
        job_id = match.group(1) if match else "unknown"

        # Update metadata
        self._update_meta(
            run_path,
            {
                "status": "submitted",
                "job_id": job_id,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "sbatch_command": " ".join(cmd),
            },
        )

        return {
            "mode": "submitted",
            "job_id": job_id,
            "command": " ".join(cmd),
            "run_dir": str(run_path),
            "message": f"Job {job_id} submitted successfully.",
        }

    # ------------------------------------------------------------------
    # 4. Get run status
    # ------------------------------------------------------------------

    def get_run_status(
        self, run_dir: str | None = None, job_id: str | None = None
    ) -> dict:
        """Check the status of a UFS experiment run."""
        if job_id:
            err = validate_job_id(job_id)
            if err:
                raise RunnerError(err)
            return self._status_from_sacct(job_id)

        if run_dir:
            err = validate_run_dir(run_dir)
            if err:
                raise RunnerError(err)
            run_path = Path(run_dir)
            meta_file = run_path / ".ufs_experiment.json"
            if not meta_file.exists():
                raise RunnerError(f"No experiment metadata in '{run_dir}'")
            meta = json.loads(meta_file.read_text())
            stored_job_id = meta.get("job_id")
            if not stored_job_id:
                return {"status": meta.get("status", "unknown"), "run_dir": run_dir}
            return self._status_from_sacct(stored_job_id)

        raise RunnerError("Provide either run_dir or job_id.")

    def _status_from_sacct(self, job_id: str) -> dict:
        """Query sacct for job status."""
        fmt = "JobID,JobName%30,State,ExitCode,Elapsed,Start,End,MaxRSS,NodeList"
        try:
            result = subprocess.run(
                ["sacct", "-j", job_id, f"--format={fmt}", "-n", "-X"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            raise RunnerError("sacct not found. Slurm may not be available.")
        except subprocess.TimeoutExpired:
            raise RunnerError("sacct timed out.")

        if not result.stdout.strip():
            return {"job_id": job_id, "status": "not_found"}

        return {"job_id": job_id, "sacct_output": result.stdout.strip()}

    # ------------------------------------------------------------------
    # 5. Cancel run
    # ------------------------------------------------------------------

    def cancel_run(self, job_id: str) -> dict:
        """Cancel a running UFS experiment."""
        err = validate_job_id(job_id)
        if err:
            raise RunnerError(err)

        try:
            result = subprocess.run(
                ["scancel", job_id],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            raise RunnerError("scancel not found. Slurm may not be available.")

        if result.returncode != 0 and result.stderr.strip():
            raise RunnerError(f"scancel failed: {result.stderr.strip()}")

        return {"job_id": job_id, "status": "cancel_requested"}

    # ------------------------------------------------------------------
    # 6. Collect outputs
    # ------------------------------------------------------------------

    def collect_outputs(self, run_dir: str) -> dict:
        """List output files from a completed UFS experiment."""
        err = validate_run_dir(run_dir)
        if err:
            raise RunnerError(err)

        run_path = Path(run_dir)
        if not run_path.is_dir():
            raise RunnerError(f"Run directory '{run_dir}' does not exist.")

        # Find output files (NetCDF, log, restart)
        output_patterns = ["*.nc", "*.out", "*.log", "*.restart", "outputs/*"]
        found: list[dict] = []

        for pattern in output_patterns:
            for f in run_path.glob(pattern):
                if f.is_file():
                    stat = f.stat()
                    found.append(
                        {
                            "path": str(f.relative_to(run_path)),
                            "size_mb": round(stat.st_size / (1024 * 1024), 2),
                            "modified": datetime.fromtimestamp(
                                stat.st_mtime
                            ).isoformat(),
                        }
                    )

        # Check Slurm log
        slurm_logs = list(run_path.glob("slurm-*.out"))
        for log in slurm_logs:
            stat = log.stat()
            found.append(
                {
                    "path": str(log.relative_to(run_path)),
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )

        # Sort by modification time, newest first
        found.sort(key=lambda x: x["modified"], reverse=True)

        return {
            "run_dir": str(run_path),
            "output_count": len(found),
            "outputs": found[:50],  # Cap at 50 files
        }

    # ------------------------------------------------------------------
    # 7. Stage input data
    # ------------------------------------------------------------------

    # File patterns per model type that should be copied from the user's
    # input directory.  Globs are resolved relative to input_dir.
    _STAGE_PATTERNS: dict[str, list[str]] = {
        "schism": [
            # Mesh / grid
            "hgrid.gr3", "hgrid.ll", "vgrid.in",
            # Bottom friction / diffusivity
            "rough.gr3", "drag.gr3", "diffmin.gr3", "diffmax.gr3",
            "windrot_geo2proj.gr3", "wwmbnd.gr3",
            # Initial conditions
            "elev.ic", "temp.ic", "salt.ic",
            # Boundary / forcing
            "elev2D.th.nc", "uv3D.th.nc", "TEM_3D.th.nc", "SAL_3D.th.nc",
            "bctides.in", "station.in",
            # ERA5 / DATM input data
            "INPUT/*.nc",
            # Executables and modules
            "ufs_model", "modulefiles/*", "module-setup.sh",
            # NUOPC / ESMF
            "fd_ufs.yaml", "noahmptable.tbl",
            # Mesh SCRIP files
            "INPUT/*SCRIP*.nc", "INPUT/*ESMF*.nc",
        ],
        "adcirc": [
            "fort.14", "fort.15", "fort.13", "fort.22",
            "INPUT/*.nc",
            "ufs_model", "modulefiles/*", "module-setup.sh",
            "fd_ufs.yaml", "noahmptable.tbl",
        ],
        "fvcom": [
            "*.msh", "*.nml",
            "INPUT/*.nc",
            "ufs_model", "modulefiles/*", "module-setup.sh",
            "fd_ufs.yaml", "noahmptable.tbl",
        ],
    }

    def _stage_input_data(
        self,
        input_dir: Path,
        run_path: Path,
        model_type: str,
    ) -> list[str]:
        """Copy required input files from *input_dir* into *run_path*.

        Uses symlinks when possible (same filesystem) to avoid duplicating
        large NetCDF files.  Falls back to a regular copy.

        Returns the list of staged file names (relative to run_path).
        """
        if not input_dir.is_dir():
            raise RunnerError(f"Input data directory '{input_dir}' does not exist.")

        patterns = self._STAGE_PATTERNS.get(model_type, [])
        staged: list[str] = []

        for pattern in patterns:
            for src in input_dir.glob(pattern):
                if not src.is_file():
                    continue
                # Preserve sub-directory structure (e.g. INPUT/era5.nc)
                rel = src.relative_to(input_dir)
                dest = run_path / rel

                # Don't overwrite files already placed by the template
                if dest.exists():
                    continue

                dest.parent.mkdir(parents=True, exist_ok=True)

                # Prefer symlinks to save disk space; fall back to copy
                try:
                    dest.symlink_to(src.resolve())
                except OSError:
                    shutil.copy2(src, dest)

                staged.append(str(rel))

        staged.sort()
        return staged

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_meta(self, run_path: Path, updates: dict) -> None:
        """Update the experiment metadata file."""
        meta_file = run_path / ".ufs_experiment.json"
        if meta_file.exists():
            meta = json.loads(meta_file.read_text())
        else:
            meta = {}
        meta.update(updates)
        meta_file.write_text(json.dumps(meta, indent=2))
