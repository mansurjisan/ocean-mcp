"""Tools for disk quota and storage usage queries."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..executor import CommandExecutor, ExecutorError
from ..server import mcp


def _get_executor(ctx: Context) -> CommandExecutor:
    return ctx.request_context.lifespan_context["executor"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def hpc_disk_quota(
    ctx: Context,
    filesystem: str | None = None,
) -> str:
    """Check disk quota for the current user.

    Shows home directory quota and scratch/work filesystem quotas.
    On Ursa: uses 'quota -Qs' for home and 'lfs quota' for Lustre.
    On Hercules/Orion: uses 'reportFSUsage' if available.

    Args:
        filesystem: Optional specific filesystem to check (e.g. '/scratch5',
            '/work', '/home'). If not provided, checks all available.
    """
    executor = _get_executor(ctx)
    sections: list[str] = []

    # Home quota
    if not filesystem or filesystem == "/home":
        try:
            output = await executor.run(["quota", "-Qs"])
            sections.append(f"## Home Quota\n```\n{output}\n```")
        except ExecutorError as e:
            sections.append(f"## Home Quota\nNot available: {e}")

    # Lustre quota for scratch filesystems
    scratch_paths = ["/scratch3", "/scratch4", "/scratch5"]
    if filesystem:
        scratch_paths = [filesystem] if filesystem.startswith("/scratch") else []

    import os
    user = os.environ.get("USER", "unknown")
    for path in scratch_paths:
        if not os.path.isdir(path):
            continue
        try:
            output = await executor.run(
                ["lfs", "quota", "-u", user, path]
            )
            sections.append(f"## {path} Quota\n```\n{output}\n```")
        except ExecutorError:
            pass  # Filesystem not available or not Lustre

    # Work filesystem (Hercules/Orion)
    work_paths = ["/work/noaa", "/work2/noaa"]
    if filesystem:
        work_paths = [filesystem] if filesystem.startswith("/work") else []

    for path in work_paths:
        if not os.path.isdir(path):
            continue
        try:
            output = await executor.run(
                ["lfs", "quota", "-u", user, path.split("/noaa")[0]]
            )
            sections.append(f"## {path} Quota\n```\n{output}\n```")
        except ExecutorError:
            pass

    # Try reportFSUsage (MSU-HPC systems)
    if not filesystem or filesystem.startswith("/work"):
        try:
            output = await executor.run(["reportFSUsage"])
            sections.append(f"## reportFSUsage\n```\n{output}\n```")
        except ExecutorError:
            pass

    if not sections:
        return "No quota information available. You may need to load the noaatools module: `module load contrib noaatools`"

    return "\n\n".join(sections)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def hpc_storage_usage(
    ctx: Context,
    directory: str,
    max_depth: int = 1,
) -> str:
    """Show disk usage summary for a directory.

    Uses 'du' to report sizes of subdirectories, sorted by size.

    Args:
        directory: Path to check (e.g. '/scratch5/purged/Mansur.Jisan').
        max_depth: How many directory levels deep to report (default 1).
    """
    import os
    import re as _re

    executor = _get_executor(ctx)

    # Validate path - no shell metacharacters
    if _re.search(r"[;&|`$(){}]", directory):
        return f"Error: Unsafe characters in path: '{directory}'"
    if not os.path.isdir(directory):
        return f"Error: Directory '{directory}' does not exist."

    depth = min(max(1, max_depth), 3)  # Cap at 3 to avoid huge output

    try:
        output = await executor.run(
            ["du", "-h", f"--max-depth={depth}", "--summarize", directory],
            timeout=60,
        )
    except ExecutorError:
        # --summarize and --max-depth conflict; try without --summarize
        try:
            output = await executor.run(
                ["du", "-h", f"--max-depth={depth}", directory],
                timeout=60,
            )
        except ExecutorError as e:
            return f"Error: {e}"

    # Sort by size (largest first) for readability
    lines = output.strip().split("\n")
    total_line = lines[-1] if lines else ""

    return (
        f"## Storage Usage: {directory}\n"
        f"```\n{output}\n```\n"
        f"\n**Total**: {total_line.split()[0] if total_line else 'unknown'}"
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def hpc_df(
    ctx: Context,
    filesystem: str | None = None,
) -> str:
    """Show filesystem disk space usage (df -h).

    Args:
        filesystem: Optional specific mount point (e.g. '/scratch5').
            If not provided, shows all mounted filesystems.
    """
    executor = _get_executor(ctx)
    cmd = ["df", "-h"]
    if filesystem:
        import re as _re
        if _re.search(r"[;&|`$(){}]", filesystem):
            return f"Error: Unsafe characters in path: '{filesystem}'"
        cmd.append(filesystem)

    try:
        output = await executor.run(cmd)
        label = filesystem or "All Filesystems"
        return f"## Disk Space: {label}\n```\n{output}\n```"
    except ExecutorError as e:
        return f"Error: {e}"
