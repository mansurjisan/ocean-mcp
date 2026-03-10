"""Tools for monitoring and managing submitted UFS experiments."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..runner import RunnerError, UfsRunner
from ..server import mcp


def _get_runner(ctx: Context) -> UfsRunner:
    return ctx.request_context.lifespan_context["ufs_runner"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def ufs_get_run_status(
    ctx: Context,
    run_dir: str | None = None,
    job_id: str | None = None,
) -> str:
    """Check the status of a UFS experiment run.

    Provide either the run directory or the Slurm job ID.

    Args:
        run_dir: Path to the experiment directory.
        job_id: Slurm job ID (if known).
    """
    try:
        runner = _get_runner(ctx)
        result = runner.get_run_status(run_dir=run_dir, job_id=job_id)

        if "sacct_output" in result:
            return (
                f"## Run Status — Job {result['job_id']}\n\n"
                f"```\n{result['sacct_output']}\n```"
            )

        return f"## Run Status\n\n- **Status**: {result.get('status', 'unknown')}"

    except RunnerError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def ufs_cancel_run(
    ctx: Context,
    job_id: str,
) -> str:
    """Cancel a running UFS experiment.

    Args:
        job_id: Slurm job ID to cancel.
    """
    try:
        runner = _get_runner(ctx)
        result = runner.cancel_run(job_id)
        return f"Cancel requested for job {result['job_id']}."

    except RunnerError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def ufs_collect_outputs(
    ctx: Context,
    run_dir: str,
) -> str:
    """List output files from a completed UFS experiment.

    Finds NetCDF outputs, log files, restart files, and Slurm logs.

    Args:
        run_dir: Path to the experiment directory.
    """
    try:
        runner = _get_runner(ctx)
        result = runner.collect_outputs(run_dir)

        if result["output_count"] == 0:
            return f"No output files found in {result['run_dir']}."

        lines = [
            f"## Experiment Outputs",
            f"- **Directory**: {result['run_dir']}",
            f"- **Files found**: {result['output_count']}",
            "",
            "| File | Size (MB) | Modified |",
            "|------|-----------|----------|",
        ]
        for f in result["outputs"]:
            lines.append(f"| {f['path']} | {f['size_mb']} | {f['modified']} |")

        return "\n".join(lines)

    except RunnerError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"
