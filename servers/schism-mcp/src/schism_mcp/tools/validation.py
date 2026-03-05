"""Validation and debugging tools for SCHISM configurations."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import SchismClient
from ..server import mcp
from ..utils import (
    match_error_pattern,
    parse_hgrid_header,
    parse_param_nml,
    parse_vgrid,
    validate_param_nml,
)


def _get_client(ctx: Context) -> SchismClient:
    return ctx.request_context.lifespan_context["schism_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def schism_validate_config(
    ctx: Context,
    param_nml_path: str | None = None,
    param_nml_content: str | None = None,
    hgrid_path: str | None = None,
    vgrid_path: str | None = None,
) -> str:
    """Validate a SCHISM configuration with comprehensive checks.

    Parses param.nml and optionally cross-references with hgrid.gr3 and vgrid.in.
    Checks nspool/ihfskip divisibility, 2D vs 3D consistency, dt adequacy,
    output frequency, and module flags.

    Args:
        param_nml_path: Path to param.nml file.
        param_nml_content: Raw text of param.nml (alternative to path).
        hgrid_path: Optional path to hgrid.gr3 for cross-validation.
        vgrid_path: Optional path to vgrid.in for cross-validation.
    """
    try:
        client = _get_client(ctx)

        # Parse param.nml
        if param_nml_content:
            nml_text = param_nml_content
        elif param_nml_path:
            nml_text = client.read_file(param_nml_path)
        else:
            return "Error: Either param_nml_path or param_nml_content must be provided."

        parsed = parse_param_nml(nml_text)

        # Parse optional companion files
        hgrid_info = None
        if hgrid_path:
            header = client.read_file_header(hgrid_path, max_lines=200)
            hgrid_info = parse_hgrid_header(header)

        vgrid_info = None
        if vgrid_path:
            vgrid_text = client.read_file(vgrid_path)
            vgrid_info = parse_vgrid(vgrid_text)

        # Run validation
        issues = validate_param_nml(parsed, hgrid_info, vgrid_info)

        # Format output
        lines = ["## SCHISM Configuration Validation"]
        if param_nml_path:
            lines.append(f"*param.nml: {param_nml_path}*")
        if hgrid_path:
            lines.append(f"*hgrid.gr3: {hgrid_path}*")
        if vgrid_path:
            lines.append(f"*vgrid.in: {vgrid_path}*")
        lines.append("")

        errors = [i for i in issues if i["severity"] == "error"]
        warnings = [i for i in issues if i["severity"] == "warning"]
        infos = [i for i in issues if i["severity"] == "info"]

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

        if not issues:
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
async def schism_diagnose_error(
    ctx: Context,
    error_text: str,
) -> str:
    """Diagnose a SCHISM run error from a log snippet or error description.

    Matches against known SCHISM failure modes (dry boundary, NaN, vertical
    instability, hotstart incompatibility, etc.) and suggests fixes.

    Args:
        error_text: Error message, log snippet, or description of the problem.
    """
    matches = match_error_pattern(error_text)

    if not matches:
        return (
            "No known error patterns matched your description.\n\n"
            "**Suggestions**:\n"
            "- Check the SCHISM mirror.out and log files for details\n"
            "- Verify all input files are consistent (matching grid, correct formats)\n"
            "- Try `schism_validate_config` to check your param.nml configuration\n"
            "- Use `schism_search_docs` to search the SCHISM documentation"
        )

    lines = ["## SCHISM Error Diagnosis"]
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
