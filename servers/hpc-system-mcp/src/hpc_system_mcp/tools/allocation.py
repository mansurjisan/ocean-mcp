"""Tools for Slurm allocation, FairShare, and accounting queries."""

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
        openWorldHint=True,
    )
)
async def hpc_allocation_usage(
    ctx: Context,
    account: str | None = None,
    cluster: str | None = None,
) -> str:
    """Show core-hour allocation usage via sreport.

    Reports how many core-hours have been used by the user or account.

    Args:
        account: Slurm account name. If not provided, shows user's own usage.
        cluster: Cluster name (e.g. 'ursa', 'hercules', 'orion').
            Auto-detected if not provided.
    """
    executor = _get_executor(ctx)
    user = os.environ.get("USER", "unknown")
    sections: list[str] = []

    # User utilization
    cmd = [
        "sreport",
        "cluster",
        "UserUtilizationByAccount",
        "-t",
        "Hours",
        f"Users={user}",
        "-n",
    ]
    if cluster:
        cmd.extend(["-M", cluster])
    try:
        output = await executor.run(cmd)
        sections.append(f"## Your Usage ({user})\n```\n{output}\n```")
    except ExecutorError as e:
        sections.append(f"## Your Usage\nNot available: {e}")

    # Account utilization (if account specified)
    if account:
        cmd = [
            "sreport",
            "cluster",
            "AccountUtilizationByUser",
            "-t",
            "Hours",
            f"account={account}",
            "-n",
        ]
        if cluster:
            cmd.extend(["-M", cluster])
        try:
            output = await executor.run(cmd)
            sections.append(f"## Account: {account}\n```\n{output}\n```")
        except ExecutorError as e:
            sections.append(f"## Account: {account}\nNot available: {e}")

    # Try saccount_params (Hera/Jet/Orion only)
    try:
        output = await executor.run(["saccount_params"])
        sections.append(f"## saccount_params\n```\n{output}\n```")
    except ExecutorError:
        pass

    # Try shpcrpt (MSU-HPC only)
    if account:
        try:
            cmd = ["shpcrpt"]
            if cluster:
                cmd.extend(["-c", cluster])
            cmd.extend(["-p", account])
            output = await executor.run(cmd)
            sections.append(f"## shpcrpt ({account})\n```\n{output}\n```")
        except ExecutorError:
            pass

    if not sections:
        return "No allocation data available. Ensure Slurm tools are accessible."

    return "\n\n".join(sections)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def hpc_fairshare(
    ctx: Context,
    account: str | None = None,
    detailed: bool = False,
) -> str:
    """Show FairShare status for Slurm accounts.

    FairShare determines job scheduling priority. A factor > 0.5 means
    underutilization (higher priority); < 0.5 means overutilization.

    Args:
        account: Specific account to check. If not provided, shows all.
        detailed: If true, show per-user breakdown within the account.
    """
    executor = _get_executor(ctx)

    cmd = ["sshare"]
    if account:
        if detailed:
            cmd.extend(["-a", "-A", account])
        else:
            cmd.extend(["-A", account])
    else:
        cmd.append("-a")

    try:
        output = await executor.run(cmd)
    except ExecutorError as e:
        return f"Error: {e}"

    header = f"## FairShare: {account or 'All Accounts'}"
    explanation = (
        "\n> **Reading FairShare**: Factor > 0.5 = underutilized (higher priority). "
        "Factor < 0.5 = overutilized (lower priority). "
        "Windfall QOS jobs do not count toward usage."
    )

    return f"{header}\n```\n{output}\n```\n{explanation}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def hpc_account_info(
    ctx: Context,
    user: str | None = None,
) -> str:
    """Show Slurm account associations for a user.

    Lists all accounts, partitions, QOS, and limits the user has access to.

    Args:
        user: Username to query. Defaults to current user.
    """
    executor = _get_executor(ctx)
    target_user = user or os.environ.get("USER", "unknown")

    try:
        output = await executor.run(
            [
                "sacctmgr",
                "show",
                "assoc",
                f"user={target_user}",
                "format=Account,Partition,QOS,MaxJobs,MaxSubmit,MaxWall,GrpTRES",
                "--parsable2",
                "--noheader",
            ]
        )
    except ExecutorError as e:
        return f"Error: {e}"

    if not output.strip():
        return f"No Slurm associations found for user '{target_user}'."

    # Parse into readable table
    lines = ["## Slurm Accounts for {}\n".format(target_user)]
    lines.append(
        "| Account | Partition | QOS | MaxJobs | MaxSubmit | MaxWall | GrpTRES |"
    )
    lines.append(
        "|---------|-----------|-----|---------|-----------|---------|---------|"
    )
    for row in output.strip().split("\n"):
        cols = row.split("|")
        if len(cols) >= 7:
            lines.append("| {} |".format(" | ".join(c.strip() for c in cols[:7])))
        else:
            # Fewer columns — just display as-is
            lines.append(f"| {row} |")

    return "\n".join(lines)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def hpc_job_priority(
    ctx: Context,
    job_id: str | None = None,
) -> str:
    """Show job priority factors for pending jobs.

    Helps understand why a job is waiting and its position in the queue.

    Args:
        job_id: Specific job ID to check. If not provided, shows all user's pending jobs.
    """
    import re

    executor = _get_executor(ctx)

    cmd = ["sprio"]
    if job_id:
        if not re.match(r"^\d+$", job_id):
            return f"Error: Invalid job ID: '{job_id}'"
        cmd.extend(["-j", job_id])
    else:
        user = os.environ.get("USER", "unknown")
        cmd.extend(["-u", user])

    try:
        output = await executor.run(cmd)
    except ExecutorError as e:
        return f"Error: {e}"

    if not output.strip():
        return "No pending jobs found."

    return f"## Job Priority\n```\n{output}\n```"
