"""Tests for MCP tool functions."""

import asyncio
import time

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


@pytest.mark.asyncio
async def test_create_experiment_tool_warns_on_unmatched_override(
    mock_ctx, tmp_path, monkeypatch
):
    """dt_ocean has no matching {{placeholder}} in the schism template —
    the tool must surface a warning instead of silently claiming success."""
    monkeypatch.setenv("UFS_RUNNER_ALLOWED_PATHS", str(tmp_path))
    run_dir = str(tmp_path / "warn_tool_test")
    result = await ufs_create_experiment(
        mock_ctx,
        model_type="schism",
        run_dir=run_dir,
        overrides='{"dt_ocean": 5.0}',
    )
    assert "Experiment Created" in result
    assert "Override Warnings" in result
    assert "dt_ocean" in result


@pytest.mark.asyncio
async def test_create_experiment_tool_no_warning_for_matched_override(
    mock_ctx, tmp_path, monkeypatch
):
    """An override that does land on a real placeholder produces no
    warning section, same as before this fix."""
    monkeypatch.setenv("UFS_RUNNER_ALLOWED_PATHS", str(tmp_path))
    run_dir = str(tmp_path / "no_warn_tool_test")
    result = await ufs_create_experiment(
        mock_ctx,
        model_type="schism",
        run_dir=run_dir,
        overrides='{"start_year": 2030}',
    )
    assert "Experiment Created" in result
    assert "Override Warnings" not in result


@pytest.mark.asyncio
async def test_create_experiment_tool_does_not_block_event_loop(
    mock_ctx, tmp_path, monkeypatch
):
    """The sync UfsRunner call must run off the event loop (asyncio.to_thread)
    so other coroutines can make progress while it's in flight — otherwise a
    slow call (e.g. a real 30s sbatch/sacct) would stall the whole server."""
    monkeypatch.setenv("UFS_RUNNER_ALLOWED_PATHS", str(tmp_path))
    runner = mock_ctx.request_context.lifespan_context["ufs_runner"]
    real_create = runner.create_experiment
    order: list[str] = []

    def slow_create(*args, **kwargs):
        order.append("sync_start")
        time.sleep(0.2)
        order.append("sync_end")
        return real_create(*args, **kwargs)

    monkeypatch.setattr(runner, "create_experiment", slow_create)

    async def concurrent_task():
        await asyncio.sleep(0.05)
        order.append("concurrent_task_ran")

    run_dir = str(tmp_path / "nonblocking_test")
    await asyncio.gather(
        ufs_create_experiment(mock_ctx, model_type="schism", run_dir=run_dir),
        concurrent_task(),
    )

    assert order.index("concurrent_task_ran") < order.index("sync_end")
