"""Tools for disk quota and storage usage queries."""

import re

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..executor import CommandExecutor, ExecutorError
from ..server import mcp


def _get_executor(ctx: Context) -> CommandExecutor:
    return ctx.request_context.lifespan_context["executor"]


_DU_TRUNCATION_MARKER = "... (truncated)"
_DU_SIZE_UNITS = {
    "": 1,
    "K": 1024,
    "M": 1024**2,
    "G": 1024**3,
    "T": 1024**4,
    "P": 1024**5,
}
_DU_SIZE_RE = re.compile(r"^([\d.]+)\s*([KMGTP]?)", re.IGNORECASE)


def _du_size_to_bytes(size_str: str) -> float:
    """Best-effort parse of a `du -h` size (e.g. '1.2G') into bytes, for sorting.

    Returns 0 for anything unparseable so a stray line just sorts last
    instead of raising.
    """
    match = _DU_SIZE_RE.match(size_str.strip())
    if not match:
        return 0.0
    number, suffix = match.groups()
    try:
        value = float(number)
    except ValueError:
        return 0.0
    return value * _DU_SIZE_UNITS.get(suffix.upper(), 1)


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
            output = await executor.run(["lfs", "quota", "-u", user, path])
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

    Uses 'du' to report sizes of subdirectories, sorted by size (largest
    first), plus the directory's overall total.

    Args:
        directory: Path to check (e.g. '/scratch5/purged/Mansur.Jisan').
        max_depth: How many directory levels deep to report (default 1).
    """
    import os

    executor = _get_executor(ctx)

    # Validate path - no shell metacharacters
    if re.search(r"[;&|`$(){}]", directory):
        return f"Error: Unsafe characters in path: '{directory}'"
    if not os.path.isdir(directory):
        return f"Error: Directory '{directory}' does not exist."

    depth = min(max(1, max_depth), 3)  # Cap at 3 to avoid huge output

    # NOTE: `--summarize` and `--max-depth` are mutually exclusive in GNU du
    # ("du: warning: summarizing conflicts with --max-depth", exit 1). That
    # used to be the primary command here — it always failed and silently
    # fell back to the equivalent command below, so every call paid for two
    # full directory traversals (expensive on a large Lustre tree).
    # `--max-depth` alone already reports the directory's own grand total as
    # its last line, so that's the only command needed.
    try:
        output = await executor.run(
            ["du", "-h", f"--max-depth={depth}", directory],
            timeout=60,
        )
    except ExecutorError as e:
        return f"Error: {e}"

    # The executor caps raw output at 10000 chars and appends this marker;
    # a tree with enough entries at this depth can exceed that. Detect it so
    # we never mistake the truncation marker (or a partial trailing line)
    # for the real total.
    was_truncated = output.endswith(_DU_TRUNCATION_MARKER)
    lines = output.strip().split("\n")
    if was_truncated:
        lines = lines[:-1]  # drop the "... (truncated)" marker line itself

    rows: list[tuple[float, str, str]] = []  # (bytes, size_str, path)
    for line in lines:
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue  # skip a stray/partial line rather than mis-render it
        size_str, path = parts
        rows.append((_du_size_to_bytes(size_str), size_str, path))

    # When the raw output was cut at the executor's char cap, the cut can
    # land mid-line: the marker line itself is already dropped above, but
    # the row immediately before it can be a path sliced off mid-name (e.g.
    # "404K\t/.../subdirectory_w") that still parses as a perfectly normal
    # two-column row. Indistinguishable from a real entry, so drop it too
    # rather than risk rendering a fabricated-looking path as real data.
    if was_truncated and rows:
        rows = rows[:-1]

    # `du` always prints the queried directory's own total last — but only
    # trust that when the output wasn't cut off, since a truncated tail
    # could be a partial number rather than the real total.
    if was_truncated or not rows:
        total_str = "unknown (output truncated — try a smaller max_depth or a more specific directory)"
        details = rows
    else:
        total_str = rows[-1][1]
        details = rows[:-1]

    details.sort(key=lambda row: row[0], reverse=True)

    max_rows = 50
    shown = details[:max_rows]
    body = (
        "\n".join(f"{size}\t{path}" for _, size, path in shown)
        if shown
        else "(no subdirectories)"
    )

    footer = ""
    if was_truncated:
        footer = (
            "\n\n*`du` output was too large and got truncated; the list "
            "below may be incomplete. Try a smaller `max_depth` or a more "
            "specific `directory`.*"
        )
    elif len(details) > max_rows:
        footer = f"\n\n*Showing {max_rows} of {len(details)} entries, largest first.*"

    return (
        f"## Storage Usage: {directory}\n"
        f"```\n{body}\n```\n"
        f"\n**Total**: {total_str}"
        f"{footer}"
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
        if re.search(r"[;&|`$(){}]", filesystem):
            return f"Error: Unsafe characters in path: '{filesystem}'"
        cmd.append(filesystem)

    try:
        output = await executor.run(cmd)
        label = filesystem or "All Filesystems"
        return f"## Disk Space: {label}\n```\n{output}\n```"
    except ExecutorError as e:
        return f"Error: {e}"
