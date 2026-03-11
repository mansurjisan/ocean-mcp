"""Tests for MCP tool functions."""

import pytest

from ufs_runner_mcp.tools.experiment import (
    ufs_create_experiment,
    ufs_validate_experiment,
    ufs_submit_experiment,
    ufs_list_templates,
)
from ufs_runner_mcp.tools.monitoring import (
    ufs_get_run_status,
    ufs_collect_outputs,
)


@pytest.mark.asyncio
async def test_create_experiment_tool(mock_ctx, tmp_path, monkeypatch):
    monkeypatch.setenv("UFS_RUNNER_ALLOWED_PATHS", str(tmp_path))
    run_dir = str(tmp_path / "tool_test")
    result = await ufs_create_experiment(
        mock_ctx,
        model_type="schism",
        run_dir=run_dir,
    )
    assert "Experiment Created" in result
    assert "param.nml" in result


@pytest.mark.asyncio
async def test_create_experiment_bad_model(mock_ctx, tmp_path, monkeypatch):
    monkeypatch.setenv("UFS_RUNNER_ALLOWED_PATHS", str(tmp_path))
    result = await ufs_create_experiment(
        mock_ctx,
        model_type="nope",
        run_dir=str(tmp_path / "x"),
    )
    assert "Error" in result


@pytest.mark.asyncio
async def test_validate_tool(mock_ctx, schism_run_dir):
    result = await ufs_validate_experiment(mock_ctx, run_dir=schism_run_dir)
    assert "Experiment Validation" in result


@pytest.mark.asyncio
async def test_submit_dry_run_tool(mock_ctx, schism_run_dir):
    result = await ufs_submit_experiment(
        mock_ctx,
        run_dir=schism_run_dir,
        account="coastal-act",
        partition="compute",
        dry_run=True,
    )
    assert "Dry Run" in result
    assert "sbatch" in result


@pytest.mark.asyncio
async def test_list_templates_tool(mock_ctx):
    result = await ufs_list_templates(mock_ctx)
    assert "schism_sandy_duck" in result


@pytest.mark.asyncio
async def test_collect_outputs_tool(mock_ctx, schism_run_dir):
    result = await ufs_collect_outputs(mock_ctx, run_dir=schism_run_dir)
    # May be empty or have template files
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_get_status_no_job(mock_ctx, schism_run_dir):
    result = await ufs_get_run_status(mock_ctx, run_dir=schism_run_dir)
    assert "Status" in result
