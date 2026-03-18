"""Tests for config diff and dependency analysis tools."""

from unittest.mock import MagicMock, patch

import pytest

from nos_workflow_mcp.tools.tracker import nos_config_diff, nos_dependency_analysis


class TestConfigDiff:
    @pytest.mark.asyncio
    async def test_config_diff_no_changes(self, mock_ctx):
        """Empty git diff output means no changes between refs."""
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = ""
        completed.stderr = ""

        with patch(
            "nos_workflow_mcp.tools.tracker.subprocess.run", return_value=completed
        ):
            result = await nos_config_diff(
                mock_ctx, system_name="secofs", ref_a="v1.0", ref_b="v1.1"
            )

        assert "No changes" in result
        assert "secofs" in result

    @pytest.mark.asyncio
    async def test_config_diff_with_changes(self, mock_ctx):
        """Non-empty git diff output is returned as a formatted diff block."""
        diff_text = (
            "--- a/parm/systems/secofs.yaml\n"
            "+++ b/parm/systems/secofs.yaml\n"
            "@@ -10,3 +10,3 @@\n"
            "-  dt: 150\n"
            "+  dt: 120\n"
        )
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = diff_text
        completed.stderr = ""

        with patch(
            "nos_workflow_mcp.tools.tracker.subprocess.run", return_value=completed
        ):
            result = await nos_config_diff(
                mock_ctx, system_name="secofs", ref_a="v1.0", ref_b="v1.1"
            )

        assert "Config Diff: secofs" in result
        assert "```diff" in result
        assert "dt: 150" in result
        assert "dt: 120" in result

    @pytest.mark.asyncio
    async def test_config_diff_unsafe_ref_rejected(self, mock_ctx):
        """Git refs with shell metacharacters are rejected."""
        result = await nos_config_diff(
            mock_ctx, system_name="secofs", ref_a="HEAD; rm -rf /", ref_b="HEAD~1"
        )
        assert "Error" in result
        assert "Unsafe characters" in result

    @pytest.mark.asyncio
    async def test_config_diff_git_error(self, mock_ctx):
        """Git returning a non-zero exit code surfaces the error."""
        completed = MagicMock()
        completed.returncode = 128
        completed.stdout = ""
        completed.stderr = "fatal: bad revision 'nonexistent'"

        with patch(
            "nos_workflow_mcp.tools.tracker.subprocess.run", return_value=completed
        ):
            result = await nos_config_diff(
                mock_ctx, system_name="secofs", ref_a="nonexistent", ref_b="HEAD"
            )

        assert "Error running git diff" in result


class TestDependencyAnalysis:
    @pytest.mark.asyncio
    async def test_dependency_analysis_dt(self, mock_ctx):
        """dt parameter should list CFL, EXTSTEP, NHIS, NSTA, NRST."""
        result = await nos_dependency_analysis(
            mock_ctx, system_name="secofs", parameter_path="model.physics.dt"
        )

        assert "Dependency Analysis" in result
        assert "secofs" in result
        assert "CFL" in result
        assert "EXTSTEP_SECONDS" in result
        assert "NHIS" in result
        assert "NSTA" in result
        assert "NRST" in result

    @pytest.mark.asyncio
    async def test_dependency_analysis_nprocs(self, mock_ctx):
        """nprocs parameter should list TOTAL_TASKS, partition, memory."""
        result = await nos_dependency_analysis(
            mock_ctx, system_name="secofs", parameter_path="resources.nprocs"
        )

        assert "TOTAL_TASKS" in result
        assert "partition" in result
        assert "memory" in result

    @pytest.mark.asyncio
    async def test_dependency_analysis_grid(self, mock_ctx):
        """grid parameter should list forcing interpolation, boundaries, stations."""
        result = await nos_dependency_analysis(
            mock_ctx, system_name="secofs", parameter_path="grid"
        )

        assert "interpolation" in result
        assert "boundary" in result
        assert "station" in result

    @pytest.mark.asyncio
    async def test_dependency_analysis_forcing(self, mock_ctx):
        """forcing parameter should list MET_NUM, variables, time resolution."""
        result = await nos_dependency_analysis(
            mock_ctx, system_name="secofs", parameter_path="forcing"
        )

        assert "MET_NUM" in result
        assert "variables" in result
        assert "time resolution" in result

    @pytest.mark.asyncio
    async def test_dependency_analysis_unknown_param(self, mock_ctx):
        """Unknown parameters return an informative message with known params."""
        result = await nos_dependency_analysis(
            mock_ctx, system_name="secofs", parameter_path="model.obscure.param"
        )

        assert "No dependency information" in result
        assert "dt" in result
        assert "nprocs" in result
        assert "grid" in result
        assert "forcing" in result
