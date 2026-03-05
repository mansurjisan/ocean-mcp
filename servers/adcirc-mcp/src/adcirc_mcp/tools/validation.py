"""Validation and debugging tools for ADCIRC configurations."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import ADCIRCClient
from ..server import mcp
from ..utils import (
    check_cfl,
    match_error_pattern,
    parse_fort13,
    parse_fort14_header,
    parse_fort15,
    validate_fort15,
)


def _get_client(ctx: Context) -> ADCIRCClient:
    return ctx.request_context.lifespan_context["adcirc_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def adcirc_validate_config(
    ctx: Context,
    fort15_path: str | None = None,
    fort15_content: str | None = None,
    fort14_path: str | None = None,
    fort13_path: str | None = None,
    min_edge_length: float | None = None,
    max_depth: float | None = None,
) -> str:
    """Validate an ADCIRC configuration with comprehensive checks.

    Parses fort.15 and optionally cross-references with fort.14 and fort.13.
    Checks CFL condition, parameter consistency, NWS/file matching,
    DRAMP adequacy, station counts, and output frequency sanity.

    Args:
        fort15_path: Path to the fort.15 file.
        fort15_content: Raw text of fort.15 (alternative to path).
        fort14_path: Optional path to fort.14 for cross-validation.
        fort13_path: Optional path to fort.13 for cross-validation.
        min_edge_length: Optional minimum mesh edge length in meters (for CFL check).
        max_depth: Optional maximum water depth in meters (for CFL check).
    """
    try:
        client = _get_client(ctx)

        # Parse fort.15
        if fort15_content:
            fort15_text = fort15_content
        elif fort15_path:
            fort15_text = client.read_file(fort15_path)
        else:
            return "Error: Either fort15_path or fort15_content must be provided."

        parsed = parse_fort15(fort15_text)

        # Parse optional companion files
        fort14_info = None
        if fort14_path:
            header = client.read_file_header(fort14_path, max_lines=50)
            fort14_info = parse_fort14_header(header)

        fort13_info = None
        if fort13_path:
            fort13_text = client.read_file(fort13_path)
            fort13_info = parse_fort13(fort13_text)

        # Run validation
        issues = validate_fort15(parsed, fort14_info, fort13_info)

        # CFL check if mesh stats provided
        cfl_result = None
        if min_edge_length and max_depth and parsed.get("DTDP"):
            cfl_result = check_cfl(parsed["DTDP"], min_edge_length, max_depth)

        # Format output
        lines = ["## ADCIRC Configuration Validation"]
        if fort15_path:
            lines.append(f"*Fort.15: {fort15_path}*")
        if fort14_path:
            lines.append(f"*Fort.14: {fort14_path}*")
        if fort13_path:
            lines.append(f"*Fort.13: {fort13_path}*")
        lines.append("")

        errors = [i for i in issues if i["severity"] == "error"]
        warnings = [i for i in issues if i["severity"] == "warning"]
        infos = [i for i in issues if i["severity"] == "info"]

        if cfl_result and "error" not in cfl_result:
            lines.append("### CFL Check")
            lines.append(f"- {cfl_result['recommendation']}")
            lines.append("")

        if errors:
            lines.append(f"### Errors ({len(errors)})")
            for issue in errors:
                lines.append(f"- **{issue['parameter']}**: {issue['message']}")
                lines.append(f"  - Fix: {issue['fix']}")
            lines.append("")

        if warnings:
            lines.append(f"### Warnings ({len(warnings)})")
            for issue in warnings:
                lines.append(f"- **{issue['parameter']}**: {issue['message']}")
                lines.append(f"  - Fix: {issue['fix']}")
            lines.append("")

        if infos:
            lines.append(f"### Info ({len(infos)})")
            for issue in infos:
                lines.append(f"- **{issue['parameter']}**: {issue['message']}")
            lines.append("")

        if not issues and not (cfl_result and not cfl_result.get("passes", True)):
            lines.append("No issues found. Configuration looks valid.")

        total = len(errors) + len(warnings) + len(infos)
        lines.append(
            f"\n*{total} issues found: {len(errors)} errors, {len(warnings)} warnings, {len(infos)} info*"
        )

        return "\n".join(lines)
    except Exception as e:
        return f"Error validating configuration: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def adcirc_diagnose_error(
    ctx: Context,
    error_text: str,
) -> str:
    """Diagnose an ADCIRC run error from a log snippet or error description.

    Matches against known ADCIRC failure patterns (CFL violation, hot-start
    issues, NWS mismatch, boundary errors, etc.) and suggests fixes.

    Args:
        error_text: Error message, log snippet, or description of the problem.
    """
    matches = match_error_pattern(error_text)

    if not matches:
        return (
            "No known error patterns matched your description.\n\n"
            "**Suggestions**:\n"
            "- Check the ADCIRC screen output (fort.6) for more details\n"
            "- Verify all input files are consistent (matching mesh, correct formats)\n"
            "- Try `adcirc_validate_config` to check your fort.15 configuration\n"
            "- Use `adcirc_search_docs` to search the ADCIRC wiki for your error"
        )

    lines = ["## ADCIRC Error Diagnosis"]
    lines.append(f"*Matched {len(matches)} known pattern(s)*\n")

    for i, match in enumerate(matches, 1):
        lines.append(f"### Pattern {i}")
        lines.append(f"**Diagnosis**: {match['diagnosis']}")
        lines.append(f"**Matched keywords**: {', '.join(match['matched_keywords'])}")
        lines.append("\n**Suggested fixes**:")
        for fix in match["fixes"]:
            lines.append(f"- {fix}")
        lines.append("")

    return "\n".join(lines)
