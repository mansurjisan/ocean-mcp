"""Tools for PBS (WCOSS2) job scheduler queries."""

import os
import re

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
async def hpc_pbs_jobs(
    ctx: Context,
) -> str:
    """Show current user's PBS jobs via qstat.

    Lists all jobs owned by the current user on a PBS/WCOSS2 system,
    including job ID, name, state, queue, and resource usage.
    """
    executor = _get_executor(ctx)
    user = os.environ.get("USER", "unknown")

    try:
        output = await executor.run(["qstat", "-u", user])
    except ExecutorError as e:
        return f"Error: {e}"

    if not output.strip():
        return "No PBS jobs found for the current user."

    return f"## PBS Jobs ({user})\n```\n{output}\n```"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def hpc_pbs_job_detail(
    ctx: Context,
    job_id: str,
) -> str:
    """Show detailed information for a specific PBS job.

    Returns full job attributes including resources requested, state,
    output/error paths, and scheduling info.

    Args:
        job_id: The PBS job identifier (e.g. '12345', '12345.svc').
    """
    executor = _get_executor(ctx)

    # Validate job_id: allow digits with optional server suffix (e.g. 12345.svc)
    if not re.match(r"^\d+(\.\w+)*$", job_id):
        return f"Error: Invalid PBS job ID: '{job_id}'"

    try:
        output = await executor.run(["qstat", "-f", job_id])
    except ExecutorError as e:
        return f"Error: {e}"

    if not output.strip():
        return f"No information found for PBS job '{job_id}'."

    return f"## PBS Job Detail: {job_id}\n```\n{output}\n```"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def hpc_pbs_nodes(
    ctx: Context,
) -> str:
    """Show PBS node status via pbsnodes.

    Displays node availability, jobs running on each node, and resource
    summary for the PBS/WCOSS2 cluster.
    """
    executor = _get_executor(ctx)

    try:
        output = await executor.run(["pbsnodes", "-aSj"])
    except ExecutorError as e:
        return f"Error: {e}"

    if not output.strip():
        return "No PBS node information available."

    return f"## PBS Node Status\n```\n{output}\n```"
