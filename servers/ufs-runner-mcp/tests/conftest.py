"""Shared test fixtures for ufs-runner-mcp."""

import pytest
from unittest.mock import MagicMock

from ufs_runner_mcp.runner import UfsRunner


@pytest.fixture
def runner(tmp_path, monkeypatch):
    """Create a UfsRunner that allows tmp_path as a run dir prefix."""
    monkeypatch.setenv("UFS_RUNNER_ALLOWED_PATHS", str(tmp_path))
    return UfsRunner()


@pytest.fixture
def mock_ctx(runner):
    """Create a mock MCP context with the runner in lifespan context."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"ufs_runner": runner}
    return ctx


@pytest.fixture
def schism_run_dir(tmp_path, runner):
    """Create a SCHISM experiment in tmp_path and return the path."""
    run_dir = str(tmp_path / "test_schism_run")
    runner.create_experiment(
        model_type="schism",
        run_dir=run_dir,
    )
    return run_dir
