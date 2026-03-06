"""Parameter lookup tools — embedded knowledge, no file I/O."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..models import (
    BC_TYPES,
    SCHISM_PARAMETERS,
    TIDAL_CONSTITUENTS,
    VGRID_TYPES,
    NamelistSection,
)
from ..server import mcp


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def schism_explain_parameter(
    ctx: Context,
    parameter: str,
) -> str:
    """Look up any SCHISM param.nml parameter by name.

    Returns namelist section, description, valid values, default,
    and common mistakes. Also covers tidal constituents, vertical
    grid types, and boundary condition types.

    Args:
        parameter: Parameter name (e.g., 'dt', 'nspool', 'ihfskip', 'M2', 'LSC2').
    """
    param_lower = parameter.lower()
    param_upper = parameter.upper()

    # Check param.nml parameters
    if param_lower in SCHISM_PARAMETERS:
        p = SCHISM_PARAMETERS[param_lower]
        lines = [f"## SCHISM Parameter: {param_lower}"]
        lines.append(f"**Section**: {p['section'].value}")
        lines.append(f"**Description**: {p['description']}")
        lines.append(f"**Type**: {p['type']}")

        if "units" in p:
            lines.append(f"**Units**: {p['units']}")
        if "valid_values" in p:
            lines.append(f"**Valid values**: {p['valid_values']}")
        if "typical_range" in p:
            lines.append(
                f"**Typical range**: {p['typical_range'][0]} to {p['typical_range'][1]}"
            )
        if "default" in p:
            lines.append(f"**Default**: {p['default']}")
        if p.get("common_errors"):
            lines.append("\n**Common errors**:")
            for err in p["common_errors"]:
                lines.append(f"- {err}")

        return "\n".join(lines)

    # Check tidal constituents
    if param_upper in TIDAL_CONSTITUENTS:
        c = TIDAL_CONSTITUENTS[param_upper]
        lines = [f"## Tidal Constituent: {param_upper}"]
        lines.append(f"**Description**: {c['description']}")
        lines.append(f"**Period**: {c['period_hours']} hours")
        return "\n".join(lines)

    # Check vertical grid types
    try:
        vgrid_id = int(parameter)
        if vgrid_id in VGRID_TYPES:
            v = VGRID_TYPES[vgrid_id]
            lines = [f"## Vertical Grid Type: {v['name']} (ivcor={vgrid_id})"]
            lines.append(f"**Description**: {v['description']}")
            return "\n".join(lines)
    except ValueError:
        pass

    # Check by name
    for vid, v in VGRID_TYPES.items():
        if param_upper == v["name"]:
            lines = [f"## Vertical Grid Type: {v['name']} (ivcor={vid})"]
            lines.append(f"**Description**: {v['description']}")
            return "\n".join(lines)

    # Check BC types
    try:
        bc_id = int(parameter)
        if bc_id in BC_TYPES:
            b = BC_TYPES[bc_id]
            lines = [f"## Boundary Condition Type {bc_id}: {b['name']}"]
            lines.append(f"**Description**: {b['description']}")
            return "\n".join(lines)
    except ValueError:
        pass

    return (
        f"Parameter '{parameter}' not found in the embedded reference.\n\n"
        "Try `schism_list_parameters` to see all available parameters, "
        "or `schism_search_docs` to search the SCHISM documentation."
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def schism_list_parameters(
    ctx: Context,
    section: str | None = None,
) -> str:
    """List all SCHISM param.nml parameters grouped by section.

    Returns a reference of parameter names with brief descriptions.

    Args:
        section: Optional filter by section ('CORE', 'OPT', 'SCHOUT').
    """
    lines = ["## SCHISM Parameter Reference"]

    # Group parameters by section
    by_section: dict[str, list[tuple[str, str]]] = {}
    for name, p in SCHISM_PARAMETERS.items():
        sect = p["section"].value
        if section and sect != section.upper():
            continue
        by_section.setdefault(sect, []).append((name, p["description"][:80]))

    if not by_section and section:
        valid = ", ".join(s.value for s in NamelistSection)
        return f"No parameters found for section '{section}'. Valid sections: {valid}"

    for sect in ["CORE", "OPT", "SCHOUT"]:
        if sect not in by_section:
            continue
        lines.append(f"\n### &{sect}")
        for name, desc in by_section[sect]:
            lines.append(f"- **{name}**: {desc}")

    if not section:
        lines.append("\n### Vertical Grid Types")
        for vid, v in VGRID_TYPES.items():
            lines.append(f"- **ivcor={vid} ({v['name']})**: {v['description']}")

        lines.append("\n### Boundary Condition Types")
        for bid, b in BC_TYPES.items():
            lines.append(f"- **Type {bid} ({b['name']})**: {b['description']}")

        lines.append("\n### Tidal Constituents")
        for name, c in TIDAL_CONSTITUENTS.items():
            lines.append(f"- **{name}**: {c['description']} ({c['period_hours']}h)")

    return "\n".join(lines)
