"""Unit tests for UfsRunner core logic."""

import json
import pytest
from pathlib import Path

from ufs_runner_mcp.runner import RunnerError
from ufs_runner_mcp.models import validate_run_dir, validate_job_id


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
        # vgrid.in already exists in the template, so it should NOT be staged
        assert "vgrid.in" not in staged
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

    def test_stage_does_not_overwrite_template(self, runner, tmp_path):
        """Template files should not be overwritten by staged files."""
        input_dir = self._make_input_dir(tmp_path)
        # Create a file in input_dir that also exists in the template
        (input_dir / "bctides.in").write_text("FROM INPUT DIR")
        run_dir = str(tmp_path / "no_overwrite")
        runner.create_experiment(
            model_type="schism",
            run_dir=run_dir,
            input_data_dir=str(input_dir),
        )
        # The template version should have been kept
        content = (Path(run_dir) / "bctides.in").read_text()
        assert content != "FROM INPUT DIR"

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
