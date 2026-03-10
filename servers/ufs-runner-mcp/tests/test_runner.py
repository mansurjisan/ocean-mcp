"""Unit tests for UfsRunner core logic."""

import json
import os
import pytest
from pathlib import Path

from ufs_runner_mcp.runner import RunnerError, UfsRunner
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

    def test_create_nonexistent_template(self, runner, tmp_path):
        with pytest.raises(RunnerError, match="Template.*not found"):
            runner.create_experiment(
                model_type="schism",
                run_dir=str(tmp_path / "x"),
                template="does_not_exist",
            )


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
