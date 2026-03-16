"""Tests for the command executor."""

import pytest

from hpc_system_mcp.executor import CommandExecutor, ExecutorError, _validate_command


class TestValidateCommand:
    """Test command validation."""

    def test_allowed_commands(self):
        assert _validate_command(["quota", "-Qs"]) is None
        assert _validate_command(["lfs", "quota", "-u", "testuser", "/scratch5"]) is None
        assert _validate_command(["sshare", "-A", "coastal-act"]) is None
        assert _validate_command(["du", "-h", "/scratch5/user"]) is None
        assert _validate_command(["id", "testuser"]) is None
        assert _validate_command(["groups", "testuser"]) is None
        assert _validate_command(["sacctmgr", "show", "assoc"]) is None
        assert _validate_command(["sreport", "cluster", "UserUtilizationByAccount"]) is None
        assert _validate_command(["sinfo"]) is None
        assert _validate_command(["df", "-h"]) is None

    def test_blocked_commands(self):
        assert _validate_command(["rm", "-rf", "/"]) is not None
        assert _validate_command(["bash", "-c", "whoami"]) is not None
        assert _validate_command(["curl", "http://evil.com"]) is not None
        assert _validate_command(["python", "-c", "import os"]) is not None
        assert _validate_command(["sbatch", "job.sh"]) is not None

    def test_shell_metacharacters_blocked(self):
        assert _validate_command(["quota", "-Qs; rm -rf /"]) is not None
        assert _validate_command(["du", "-h", "$(whoami)"]) is not None
        assert _validate_command(["lfs", "quota", "-u", "user|cat"]) is not None
        assert _validate_command(["id", "`whoami`"]) is not None

    def test_empty_command(self):
        assert _validate_command([]) is not None


class TestCommandExecutor:
    """Test the executor (using commands available locally)."""

    @pytest.mark.asyncio
    async def test_run_id(self, executor):
        """'id' should be available on any Linux system."""
        output = await executor.run(["id"])
        assert "uid=" in output

    @pytest.mark.asyncio
    async def test_run_groups(self, executor):
        """'groups' should be available on any Linux system."""
        output = await executor.run(["groups"])
        assert len(output) > 0

    @pytest.mark.asyncio
    async def test_run_df(self, executor):
        output = await executor.run(["df", "-h", "/tmp"])
        assert "Filesystem" in output or "/tmp" in output

    @pytest.mark.asyncio
    async def test_blocked_command_raises(self, executor):
        with pytest.raises(ExecutorError, match="not in the allowed list"):
            await executor.run(["rm", "-rf", "/"])

    @pytest.mark.asyncio
    async def test_shell_injection_blocked(self, executor):
        with pytest.raises(ExecutorError, match="Unsafe characters"):
            await executor.run(["id", "user; rm -rf /"])

    @pytest.mark.asyncio
    async def test_run_shell_only_module(self, executor):
        """run_shell should reject non-module commands."""
        with pytest.raises(ExecutorError, match="only supports 'module'"):
            await executor.run_shell("rm -rf /")

    @pytest.mark.asyncio
    async def test_not_found_command(self, executor):
        with pytest.raises(ExecutorError, match="not found"):
            await executor.run(["saccount_params"])  # Won't exist locally
