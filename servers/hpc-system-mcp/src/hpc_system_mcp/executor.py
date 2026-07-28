"""Safe command executor for HPC system queries."""

from __future__ import annotations

import asyncio
import contextlib
import os
import re
import shutil
import signal


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


# Bound on the reap itself: how long we'll wait for a killed process (group)
# to actually exit and close its pipes before giving up. Without this bound,
# reaping a timed-out subprocess can itself hang indefinitely (see
# _kill_and_reap docstring), turning a bounded timeout into no timeout at all.
_REAP_TIMEOUT = 5


async def _kill_and_reap(proc: asyncio.subprocess.Process) -> None:
    """Best-effort cleanup of a subprocess after its await timed out (or the
    task awaiting it was cancelled).

    ``asyncio.wait_for`` only cancels our *await* on ``communicate()`` — the
    child process itself keeps running in the background (e.g. a `du`
    walking a large Lustre tree can run for minutes after the tool call
    already returned an error), and its pipes stay open. Kill and reap it
    so nothing is orphaned.

    Two things make a naive kill()+wait() insufficient here, both hit in
    practice on this server's own tools:

    1. A child blocked in uninterruptible (D) state on a hung network
       filesystem read (e.g. `du` against a stalled Lustre/NFS mount, see
       hpc_storage_usage) does not respond to SIGKILL until the kernel
       unblocks it — a plain ``await proc.wait()`` can then block far
       longer than the timeout that triggered the kill.
    2. A grandchild that inherited the child's stdout/stderr pipes (e.g.
       run_module's `bash -c` spawning Lmod's lua/tcl helper for `module
       spider` on a large module tree) keeps those pipes open even after
       the direct child is killed, so ``proc.wait()`` — which waits for
       pipe EOF, not just process exit — can hang forever even though the
       direct child is already dead.

    Both call sites launch their subprocess with ``start_new_session=True``
    so the child is its own process group leader; killing the whole group
    (rather than just the direct child) reaches case-2 grandchildren too.
    And the reap itself is bounded by ``_REAP_TIMEOUT`` so case-1 can never
    turn a bounded tool timeout into an indefinite hang — at worst we give
    up on the reap and return, leaking the D-state process until the
    filesystem unblocks it, which is the best any caller can do.
    """
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except ProcessLookupError:
        pass  # process (group) already exited
    with contextlib.suppress(asyncio.TimeoutError):
        await asyncio.wait_for(proc.wait(), timeout=_REAP_TIMEOUT)


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
                start_new_session=True,  # own process group; see _kill_and_reap
            )
        except FileNotFoundError:
            raise ExecutorError(f"Command not found: {cmd[0]}")

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            await _kill_and_reap(proc)
            raise ExecutorError(f"Command timed out after {timeout}s: {' '.join(cmd)}")
        except asyncio.CancelledError:
            # e.g. an MCP client disconnecting mid-call. Clean up the child
            # before letting cancellation propagate — don't swallow it.
            await _kill_and_reap(proc)
            raise

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

        proc = await asyncio.create_subprocess_exec(
            "bash",
            "-c",
            script,
            "bash",  # $0
            *args,  # $1.. — never shell-parsed
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,  # own process group; see _kill_and_reap
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            await _kill_and_reap(proc)
            raise ExecutorError(f"Module command timed out: module {action}")
        except asyncio.CancelledError:
            # e.g. an MCP client disconnecting mid-call. Clean up the child
            # (and, per _kill_and_reap, its Lmod grandchildren) before
            # letting cancellation propagate — don't swallow it.
            await _kill_and_reap(proc)
            raise

        # module list/avail write to stderr
        output = stdout.decode(errors="replace").strip()
        err_output = stderr.decode(errors="replace").strip()
        combined = output or err_output
        if len(combined) > 10000:
            combined = combined[:10000] + "\n... (truncated)"
        return combined
