"""Tools for diagnosing NOS OFS run failures."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..config_reader import ConfigReader
from ..server import mcp


def _get_reader(ctx: Context) -> ConfigReader:
    return ctx.request_context.lifespan_context["config_reader"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def nos_diagnose_failure(
    ctx: Context,
    log_content: str,
) -> str:
    """Diagnose a NOS OFS model run failure from log output.

    Pass the contents of a job log file, fatal.error, or relevant error
    output. The tool will classify the error and suggest fixes.

    Handles SCHISM-specific errors (h_c, CFL, NaN), MPI failures,
    OOM, timeout, missing files, and general model aborts.

    Args:
        log_content: Contents of the error log or fatal.error file.
    """
    reader = _get_reader(ctx)
    diagnosis = reader.diagnose_log(log_content)

    lines = ["## Failure Diagnosis\n"]
    lines.append(f"**Error Type:** {diagnosis['error_type']}")
    if diagnosis["error_message"]:
        lines.append(f"\n**Details:** {diagnosis['error_message']}")
    if diagnosis["suggestion"]:
        lines.append(f"\n**Suggested Fix:** {diagnosis['suggestion']}")

    return "\n".join(lines)
