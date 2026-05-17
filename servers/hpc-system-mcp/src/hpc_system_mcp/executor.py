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
    "quota",
    "lfs",
    "du",
    "df",
    "sacctmgr",
    "sshare",
    "sreport",
    "sinfo",
    "squeue",
    "sacct",
    "sprio",
    "sbatch-limits",
    "saccount_params",
    "reportFSUsage",
    "shpcrpt",
    "module",
    "id",
    "groups",
    # PBS / WCOSS2
    "qstat",
    "qsub",
    "qdel",
    "qselect",
    "pbsnodes",
}


# Lmod subcommands the module tools are allowed to invoke (not user input,
# but validated defensively).
_ALLOWED_MODULE_ACTIONS = {"list", "avail", "spider", "show"}

# A user-supplied module name / search token. Real names look like
# 'netcdf-c/4.9.2', 'intel/2023.2.0', 'cray-mpich/8.1.25', 'netcdf-c@4.9.2'.
# Allow only word chars, dot, slash, plus, at, hyphen — NO whitespace,
# shell metacharacters, redirection, newline, or glob. (The previous
# per-tool denylist `[;&|` $(){}]` missed `>`, spaces, newlines, `*?` ...)
_MODULE_TOKEN_RE = re.compile(r"^[\w.+@/-]+$")


def validate_module_token(value: str) -> str | None:
    """Validate a user-supplied module name/search token.

    Returns None if safe, else an error message. Defense in depth: even an
    invalid token cannot inject, because run_module passes it as a bash
    positional parameter, never interpolated into the script.
    """
    if not value or not _MODULE_TOKEN_RE.match(value):
        return (
            f"Invalid module token '{value}': only letters, digits, and "
            f"'. / + @ -' are allowed (no spaces or shell metacharacters)."
        )
    return None


def _validate_command(cmd: list[str]) -> str | None:
    """Check that the command is in the allowlist.

    Returns None if valid, error message if not.
    """
    if not cmd:
        return "Empty command"
    base = os.path.basename(cmd[0])
    if base not in _ALLOWED_COMMANDS:
        return (
            f"Command '{base}' is not in the allowed list: {sorted(_ALLOWED_COMMANDS)}"
        )
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
                proc.communicate(),
                timeout=timeout,
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

    async def run_module(
        self, action: str, target: str | None = None, timeout: int = 30
    ) -> str:
        """Run an Lmod `module` subcommand safely.

        `module` is a shell function (from sourcing modules.sh), so it needs a
        shell — but the *fixed* script below references the user value only as
        the positional parameter "$1", which bash never re-parses as code.
        Combined with validate_module_token(), this closes the previous
        shell-injection hole (run_shell built `source …; module <user>` and
        ran it through create_subprocess_shell with only an incomplete
        `[;&|` $(){}]` denylist — `>`, whitespace, newline, globs all slipped
        through).
        """
        if action not in _ALLOWED_MODULE_ACTIONS:
            raise ExecutorError(
                f"Unsupported module action '{action}'. "
                f"Allowed: {sorted(_ALLOWED_MODULE_ACTIONS)}"
            )
        args: list[str] = []
        if target is not None:
            err = validate_module_token(target)
            if err:
                raise ExecutorError(err)
            args = [target]

        # action is from the internal allowlist above (never user input), so
        # interpolating it is safe; the untrusted value is passed as $1.
        script = (
            f'source /etc/profile.d/modules.sh 2>/dev/null; module {action} "$@" 2>&1'
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                "bash",
                "-c",
                script,
                "bash",  # $0
                *args,  # $1.. — never shell-parsed
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            raise ExecutorError(f"Module command timed out: module {action}")

        # module list/avail write to stderr
        output = stdout.decode(errors="replace").strip()
        err_output = stderr.decode(errors="replace").strip()
        combined = output or err_output
        if len(combined) > 10000:
            combined = combined[:10000] + "\n... (truncated)"
        return combined
