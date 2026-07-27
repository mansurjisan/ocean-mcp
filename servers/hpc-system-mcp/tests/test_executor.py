"""Tests for the command executor."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from hpc_system_mcp.executor import (
    ExecutorError,
    _validate_command,
    validate_module_token,
)


class TestValidateCommand:
    """Test command validation."""

    def test_allowed_commands(self):
        assert _validate_command(["quota", "-Qs"]) is None
        assert (
            _validate_command(["lfs", "quota", "-u", "testuser", "/scratch5"]) is None
        )
        assert _validate_command(["sshare", "-A", "coastal-act"]) is None
        assert _validate_command(["du", "-h", "/scratch5/user"]) is None
        assert _validate_command(["id", "testuser"]) is None
        assert _validate_command(["groups", "testuser"]) is None
        assert _validate_command(["sacctmgr", "show", "assoc"]) is None
        assert (
            _validate_command(["sreport", "cluster", "UserUtilizationByAccount"])
            is None
        )
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

    def test_qsub_qdel_not_allowlisted(self):
        """This server is read-only/query-only — qsub/qdel are removed from
        the allowlist since no tool constructs them and qdel can delete
        another user's job if the executing account has permission."""
        assert _validate_command(["qsub", "job.sh"]) is not None
        assert _validate_command(["qdel", "12345"]) is not None


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
    async def test_run_module_rejects_unknown_action(self, executor):
        """Only the internal action allowlist is permitted."""
        with pytest.raises(ExecutorError, match="Unsupported module action"):
            await executor.run_module("load")  # load could mutate env
        with pytest.raises(ExecutorError, match="Unsupported module action"):
            await executor.run_module("rm -rf /")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "evil",
        [
            "netcdf; rm -rf /",  # blocked by old denylist too
            "x > /home/victim/.bashrc",  # redirection — old denylist MISSED
            "x -c 'id'",  # space/quote — old denylist MISSED
            "a\nrm -rf ~",  # newline — old denylist MISSED
            "net*",  # glob — old denylist MISSED
            "`id`",
            "$(whoami)",
            "a|b",
        ],
    )
    async def test_run_module_rejects_injection_token(self, executor, evil):
        """Every injection/redirection/glob token is rejected (strict allowlist)."""
        with pytest.raises(ExecutorError, match="Invalid module token"):
            await executor.run_module("show", evil)

    @pytest.mark.asyncio
    async def test_run_module_valid_token_does_not_raise(self, executor):
        """A valid token passes validation and runs (no Lmod -> empty, no crash)."""
        # Should not raise on validation; module may be absent on the test host.
        result = await executor.run_module("show", "netcdf-c/4.9.2")
        assert isinstance(result, str)

    def test_validate_module_token(self):
        """The shared token validator: strict allowlist."""
        assert validate_module_token("netcdf-c/4.9.2") is None
        assert validate_module_token("intel/2023.2.0") is None
        assert validate_module_token("netcdf-c@4.9.2") is None
        assert validate_module_token("gcc+mpi") is None
        for bad in [
            "x; rm -rf /",
            "x > /etc/passwd",
            "a b",
            "a\nb",
            "net*",
            "`id`",
            "$(id)",
            "a|b",
            "",
        ]:
            assert validate_module_token(bad) is not None, bad

    @pytest.mark.asyncio
    async def test_not_found_command(self, executor):
        with pytest.raises(ExecutorError, match="not found"):
            await executor.run(["saccount_params"])  # Won't exist locally


class TestTimeoutOrphanCleanup:
    """A command that times out must not leave an orphaned subprocess.

    ``asyncio.wait_for`` only cancels our *await* on ``communicate()`` — the
    child process itself keeps running in the background unless explicitly
    killed and reaped. Both timeout sites (run, run_module) must do this.
    """

    @staticmethod
    def _mock_slow_proc() -> MagicMock:
        mock_proc = MagicMock()
        mock_proc.kill = MagicMock()
        mock_proc.wait = AsyncMock(return_value=-9)

        async def _slow_communicate():
            await asyncio.sleep(10)
            return b"", b""

        mock_proc.communicate = _slow_communicate
        return mock_proc

    @pytest.mark.asyncio
    async def test_run_kills_and_reaps_on_timeout(self, executor, monkeypatch):
        mock_proc = self._mock_slow_proc()

        async def _fake_create_subprocess_exec(*args, **kwargs):
            return mock_proc

        monkeypatch.setattr(
            "hpc_system_mcp.executor.asyncio.create_subprocess_exec",
            _fake_create_subprocess_exec,
        )

        with pytest.raises(ExecutorError, match="timed out"):
            await executor.run(["id"], timeout=0.05)

        mock_proc.kill.assert_called_once()
        mock_proc.wait.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_module_kills_and_reaps_on_timeout(self, executor, monkeypatch):
        mock_proc = self._mock_slow_proc()

        async def _fake_create_subprocess_exec(*args, **kwargs):
            return mock_proc

        monkeypatch.setattr(
            "hpc_system_mcp.executor.asyncio.create_subprocess_exec",
            _fake_create_subprocess_exec,
        )

        with pytest.raises(ExecutorError, match="Module command timed out"):
            await executor.run_module("list", timeout=0.05)

        mock_proc.kill.assert_called_once()
        mock_proc.wait.assert_awaited_once()
