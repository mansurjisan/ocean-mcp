"""Parameter lookup tools — embedded knowledge, no file I/O."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..models import (
    ADCIRC_PARAMETERS,
    NWS_VALUES,
    NODAL_ATTRIBUTES,
    TIDAL_CONSTITUENTS,
    ParamCategory,
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
async def adcirc_explain_parameter(
    ctx: Context,
    parameter: str,
) -> str:
    """Look up any ADCIRC fort.15 parameter by name.

    Returns description, valid values, typical range, common pitfalls,
    and companion file requirements. Also covers NWS values, tidal
    constituents, and nodal attributes.

    Args:
        parameter: Parameter name (e.g., 'NWS', 'DTDP', 'TAU0', 'M2', 'mannings_n_at_sea_floor').
    """
    param_upper = parameter.upper()
    param_lower = parameter.lower()

    # Check fort.15 parameters
    if param_upper in ADCIRC_PARAMETERS:
        p = ADCIRC_PARAMETERS[param_upper]
        lines = [f"## ADCIRC Parameter: {param_upper}"]
        lines.append(f"**Description**: {p['description']}")
        lines.append(f"**Category**: {p['category'].value}")
        lines.append(f"**Type**: {p['type']}")

        if "units" in p:
            lines.append(f"**Units**: {p['units']}")
        if "valid_values" in p:
            lines.append(f"**Valid values**: {p['valid_values']}")
        if "typical_range" in p:
            lines.append(
                f"**Typical range**: {p['typical_range'][0]} to {p['typical_range'][1]}"
            )
        if p.get("common_errors"):
            lines.append("\n**Common errors**:")
            for err in p["common_errors"]:
                lines.append(f"- {err}")
        if p.get("companion_files"):
            lines.append(f"\n**Companion files**: {', '.join(p['companion_files'])}")

        # Special: if this is NWS, show all NWS values
        if param_upper == "NWS":
            lines.append("\n### NWS Value Reference")
            for val, info in sorted(NWS_VALUES.items(), key=lambda x: abs(x[0])):
                files = (
                    ", ".join(info["files_required"])
                    if info["files_required"]
                    else "none"
                )
                lines.append(f"- **NWS={val}**: {info['description']} (files: {files})")

        return "\n".join(lines)

    # Check NWS values (numeric lookup)
    try:
        nws_val = int(parameter)
        if nws_val in NWS_VALUES:
            info = NWS_VALUES[nws_val]
            lines = [f"## NWS={nws_val}"]
            lines.append(f"**Description**: {info['description']}")
            files = (
                ", ".join(info["files_required"]) if info["files_required"] else "none"
            )
            lines.append(f"**Required files**: {files}")
            return "\n".join(lines)
    except ValueError:
        pass

    # Check tidal constituents
    if param_upper in TIDAL_CONSTITUENTS:
        c = TIDAL_CONSTITUENTS[param_upper]
        lines = [f"## Tidal Constituent: {param_upper}"]
        lines.append(f"**Description**: {c['description']}")
        lines.append(f"**Period**: {c['period_hours']} hours")
        return "\n".join(lines)

    # Check nodal attributes
    if param_lower in NODAL_ATTRIBUTES:
        a = NODAL_ATTRIBUTES[param_lower]
        lines = [f"## Nodal Attribute: {param_lower}"]
        lines.append(f"**Description**: {a['description']}")
        lines.append(f"**Units**: {a['units']}")
        lines.append(
            f"**Typical range**: {a['typical_range'][0]} to {a['typical_range'][1]}"
        )
        lines.append(f"**Default value**: {a['default_value']}")
        return "\n".join(lines)

    return (
        f"Parameter '{parameter}' not found in the embedded reference.\n\n"
        "Try `adcirc_list_parameters` to see all available parameters, "
        "or `adcirc_search_docs` to search the ADCIRC wiki."
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def adcirc_list_parameters(
    ctx: Context,
    category: str | None = None,
) -> str:
    """List all ADCIRC fort.15 parameters grouped by category.

    Returns a cheat sheet of parameter names with brief descriptions.
    Also lists tidal constituents and nodal attributes.

    Args:
        category: Optional filter by category (e.g., 'time_stepping', 'forcing', 'friction', 'output', 'tidal', 'solver', 'wetting_drying', 'spatial', 'meteorological').
    """
    lines = ["## ADCIRC Parameter Reference"]

    # Group parameters by category
    by_category: dict[str, list[tuple[str, str]]] = {}
    for name, p in ADCIRC_PARAMETERS.items():
        cat = p["category"].value
        if category and cat != category:
            continue
        by_category.setdefault(cat, []).append((name, p["description"][:80]))

    if not by_category and category:
        return f"No parameters found for category '{category}'. Valid categories: {', '.join(c.value for c in ParamCategory)}"

    for cat in sorted(by_category.keys()):
        lines.append(f"\n### {cat.replace('_', ' ').title()}")
        for name, desc in by_category[cat]:
            lines.append(f"- **{name}**: {desc}")

    if not category:
        # Also list tidal constituents
        lines.append("\n### Tidal Constituents")
        for name, c in TIDAL_CONSTITUENTS.items():
            lines.append(f"- **{name}**: {c['description']} ({c['period_hours']}h)")

        # Also list nodal attributes
        lines.append("\n### Nodal Attributes (fort.13)")
        for name, a in NODAL_ATTRIBUTES.items():
            lines.append(f"- **{name}**: {a['description'][:60]}")

    return "\n".join(lines)
