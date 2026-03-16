"""Safe command executor for HPC system queries."""

from __future__ import annotations

import asyncio
import os
import re
import shutil


class ExecutorError(Exception):
    """Raised when a command execution fails."""


# Commands that are safe to run (read-only HPC queries)
_ALLOWED_COMMANDS = {
    "quota", "lfs", "du", "df",
    "sacctmgr", "sshare", "sreport", "sinfo", "squeue", "sacct",
    "sprio", "sbatch-limits",
    "saccount_params", "reportFSUsage", "shpcrpt",
    "module", "id", "groups",
}


def _validate_command(cmd: list[str]) -> str | None:
    """Check that the command is in the allowlist.

    Returns None if valid, error message if not.
    """
    if not cmd:
        return "Empty command"
    base = os.path.basename(cmd[0])
    if base not in _ALLOWED_COMMANDS:
        return f"Command '{base}' is not in the allowed list: {sorted(_ALLOWED_COMMANDS)}"
    # Block shell metacharacters in arguments
    for arg in cmd[1:]:
        if re.search(r"[;&|`$(){}]", arg):
            return f"Unsafe characters in argument: '{arg}'"
    return None


class CommandExecutor:
    """Runs whitelisted HPC commands and returns their output."""

    async def run(
        self,
        cmd: list[str],
        timeout: int = 30,
        env_extra: dict[str, str] | None = None,
    ) -> str:
        """Execute a command and return stdout.

        Raises ExecutorError on failure.
        """
        err = _validate_command(cmd)
        if err:
            raise ExecutorError(err)

        # Check that the binary exists
        if not shutil.which(cmd[0]):
            raise ExecutorError(
                f"'{cmd[0]}' not found. "
                f"It may not be available on this system or needs 'module load'."
            )

        env = dict(os.environ)
        if env_extra:
            env.update(env_extra)

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise ExecutorError(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        except FileNotFoundError:
            raise ExecutorError(f"Command not found: {cmd[0]}")

        if proc.returncode != 0:
            err_msg = stderr.decode(errors="replace").strip()
            if err_msg:
                raise ExecutorError(f"Command failed (rc={proc.returncode}): {err_msg}")
            raise ExecutorError(f"Command failed with return code {proc.returncode}")

        output = stdout.decode(errors="replace").strip()
        # Cap output to avoid overwhelming the LLM context
        if len(output) > 10000:
            output = output[:10000] + "\n... (truncated)"
        return output

    async def run_shell(self, shell_cmd: str, timeout: int = 30) -> str:
        """Run a shell command string (for module commands that need shell eval).

        Only used internally for module commands which require shell sourcing.
        """
        # Extra safety: only allow module-related shell commands
        if not shell_cmd.startswith("module "):
            raise ExecutorError("run_shell only supports 'module' commands")

        bash_cmd = f"source /etc/profile.d/modules.sh 2>/dev/null; {shell_cmd}"

        try:
            proc = await asyncio.create_subprocess_shell(
                bash_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise ExecutorError(f"Module command timed out: {shell_cmd}")

        # module list/avail write to stderr
        output = stdout.decode(errors="replace").strip()
        err_output = stderr.decode(errors="replace").strip()
        combined = output or err_output
        if len(combined) > 10000:
            combined = combined[:10000] + "\n... (truncated)"
        return combined
