"""Tools for HPC system info — partitions, nodes, groups."""

import os

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
async def hpc_system_info(
    ctx: Context,
    partition: str | None = None,
) -> str:
    """Show HPC partition and node information via sinfo.

    Displays available partitions, node counts, states, and limits.

    Args:
        partition: Specific partition to query (e.g. 'u1-compute', 'hercules').
            If not provided, shows all partitions.
    """
    import re

    executor = _get_executor(ctx)

    cmd = ["sinfo",
           "-O", "partition:20,available:6,nodes:8,cpus:8,memory:12,timelimit:12,statecompact:10,nodelist:30"]
    if partition:
        if re.search(r"[;&|`$(){}]", partition):
            return f"Error: Unsafe characters in partition: '{partition}'"
        cmd.extend(["-p", partition])

    try:
        output = await executor.run(cmd)
    except ExecutorError as e:
        return f"Error: {e}"

    label = partition or "All Partitions"
    return f"## System Info: {label}\n```\n{output}\n```"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def hpc_partition_limits(
    ctx: Context,
) -> str:
    """Show partition and QOS limits (max nodes, wall time, etc.).

    Uses 'sbatch-limits' if available (MSU-HPC systems), otherwise
    parses sinfo for basic partition limits.
    """
    executor = _get_executor(ctx)

    # Try sbatch-limits first (Hercules/Orion)
    try:
        output = await executor.run(["sbatch-limits"])
        return f"## Partition & QOS Limits\n```\n{output}\n```"
    except ExecutorError:
        pass

    # Fallback to sinfo partition summary
    try:
        output = await executor.run([
            "sinfo", "-O",
            "partition:20,timelimit:12,nodes:8,maxcpuspernode:8,defaulttime:12",
        ])
        return f"## Partition Limits (via sinfo)\n```\n{output}\n```"
    except ExecutorError as e:
        return f"Error: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def hpc_user_groups(
    ctx: Context,
    user: str | None = None,
) -> str:
    """Show group membership for a user.

    Displays the user's primary and secondary groups, which determine
    access to project directories and Slurm accounts.

    Args:
        user: Username to query. Defaults to current user.
    """
    import re

    executor = _get_executor(ctx)
    target_user = user or os.environ.get("USER", "unknown")

    if re.search(r"[;&|`$(){}]", target_user):
        return f"Error: Unsafe characters in username: '{target_user}'"

    try:
        id_output = await executor.run(["id", target_user])
    except ExecutorError as e:
        return f"Error: {e}"

    try:
        groups_output = await executor.run(["groups", target_user])
    except ExecutorError:
        groups_output = ""

    sections = [f"## User: {target_user}", f"```\n{id_output}\n```"]
    if groups_output:
        sections.append(f"### Groups\n```\n{groups_output}\n```")

    return "\n\n".join(sections)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def hpc_recent_jobs(
    ctx: Context,
    days: int = 1,
    account: str | None = None,
) -> str:
    """Show recently completed jobs via sacct.

    Args:
        days: How many days back to look (default 1, max 30).
        account: Filter by Slurm account. If not provided, shows all user's jobs.
    """
    import re
    from datetime import datetime, timedelta, timezone

    executor = _get_executor(ctx)
    days = min(max(1, days), 30)

    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    user = os.environ.get("USER", "unknown")

    cmd = [
        "sacct",
        "--user", user,
        "--starttime", start_date,
        "-X",  # No job steps
        "--format=JobID,JobName%30,Partition,Account,AllocCPUS,State,Elapsed,MaxRSS,ExitCode",
    ]
    if account:
        if re.search(r"[;&|`$(){}]", account):
            return f"Error: Unsafe characters in account: '{account}'"
        cmd.extend(["--account", account])

    try:
        output = await executor.run(cmd)
    except ExecutorError as e:
        return f"Error: {e}"

    if not output.strip():
        return f"No jobs found in the last {days} day(s)."

    return f"## Recent Jobs (last {days} day{'s' if days > 1 else ''})\n```\n{output}\n```"
