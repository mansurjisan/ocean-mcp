"""Tools for reading and comparing NOS OFS configurations."""

import yaml
from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..config_reader import ConfigError, ConfigReader
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
async def nos_list_systems(ctx: Context) -> str:
    """List all available NOS Operational Forecast Systems.

    Shows each OFS with its ocean model (SCHISM, ROMS, FVCOM, ADCIRC),
    framework (STOFS or COMF/nosofs), and geographic region.
    """
    reader = _get_reader(ctx)
    try:
        systems = reader.list_systems()
    except ConfigError as e:
        return f"Error: {e}"

    lines = ["## NOS Operational Forecast Systems\n"]
    lines.append("| System | Model | Framework | Region |")
    lines.append("|--------|-------|-----------|--------|")
    for s in systems:
        lines.append(
            f"| {s['name']} | {s['model']} | {s['framework']} | {s['region']} |"
        )

    lines.append(f"\n**{len(systems)} systems available.**")
    return "\n".join(lines)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def nos_get_config(
    ctx: Context,
    system_name: str,
    section: str | None = None,
) -> str:
    """Read the configuration for a NOS OFS system.

    Returns the full YAML config or a specific section. Configs include
    grid dimensions, forcing sources, model physics, runtime settings,
    output configuration, and ensemble parameters.

    Args:
        system_name: OFS system name (e.g. 'secofs', 'stofs_3d_atl', 'cbofs').
        section: Optional section path using dot notation (e.g. 'forcing',
            'model.physics', 'grid.domain', 'ensemble', 'resources').
            If not provided, returns the full config.
    """
    reader = _get_reader(ctx)
    try:
        if section:
            result = reader.get_config_section(system_name, section)
            if result is None:
                return f"Section '{section}' not found in {system_name} config."
            header = f"## {system_name} — {section}\n"
            return header + f"```yaml\n{yaml.dump(result, default_flow_style=False)}```"
        else:
            config = reader.get_config(system_name)
            return f"## {system_name} Configuration\n```yaml\n{yaml.dump(config, default_flow_style=False)}```"
    except ConfigError as e:
        return f"Error: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def nos_compare_configs(
    ctx: Context,
    system_a: str,
    system_b: str,
    sections: str | None = None,
) -> str:
    """Compare two NOS OFS system configurations side by side.

    Highlights differences in grid, forcing, physics, resources, and output
    settings between two systems.

    Args:
        system_a: First OFS system name (e.g. 'secofs').
        system_b: Second OFS system name (e.g. 'stofs_3d_atl').
        sections: Comma-separated sections to compare
            (default: 'grid,forcing,model,resources,output').
    """
    reader = _get_reader(ctx)
    section_list = [s.strip() for s in sections.split(",")] if sections else None

    try:
        result = reader.compare_configs(system_a, system_b, section_list)
    except ConfigError as e:
        return f"Error: {e}"

    lines = [f"## Config Comparison: {system_a} vs {system_b}\n"]

    if result["identical_sections"]:
        lines.append(
            f"**Identical sections:** {', '.join(result['identical_sections'])}\n"
        )

    if not result["differences"]:
        lines.append("No differences found in the compared sections.")
        return "\n".join(lines)

    for section, diff in result["differences"].items():
        lines.append(f"### {section}")
        lines.append(f"\n**{system_a}:**")
        lines.append(
            f"```yaml\n{yaml.dump(diff[system_a], default_flow_style=False)}```"
        )
        lines.append(f"**{system_b}:**")
        lines.append(
            f"```yaml\n{yaml.dump(diff[system_b], default_flow_style=False)}```"
        )

    return "\n".join(lines)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def nos_get_ecflow_suite(
    ctx: Context,
    system_name: str | None = None,
) -> str:
    """Show the ecFlow suite definition for NOS OFS workflows.

    Displays task dependencies, triggers, resources, and cron schedules
    from the ecFlow suite definition.

    Args:
        system_name: Optional OFS system name to filter (e.g. 'stofs_3d_atl').
            If not provided, shows the full suite structure.
    """
    reader = _get_reader(ctx)
    try:
        content = reader.get_ecflow_suite(system_name)
    except ConfigError as e:
        return f"Error: {e}"

    # Truncate if very long
    if len(content) > 5000:
        content = (
            content[:5000]
            + "\n\n... (truncated — specify a system_name to see details)"
        )

    label = system_name or "full suite"
    return f"## ecFlow Suite: {label}\n```\n{content}\n```"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def nos_get_ensemble_config(
    ctx: Context,
    system_name: str,
) -> str:
    """Show ensemble configuration for an OFS system.

    Displays ensemble members, atmospheric forcing sources (GEFS, RRFS),
    perturbed physics parameters, and resource settings.

    Args:
        system_name: OFS system name (e.g. 'secofs', 'stofs_3d_atl').
    """
    reader = _get_reader(ctx)
    try:
        ensemble = reader.get_ensemble_config(system_name)
    except ConfigError as e:
        return f"Error: {e}"

    if not ensemble:
        return f"No ensemble configuration found for {system_name}."

    return f"## Ensemble Config: {system_name}\n```yaml\n{yaml.dump(ensemble, default_flow_style=False)}```"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def nos_get_domain_bounds(
    ctx: Context,
    system_name: str,
) -> str:
    """Get the geographic domain bounds for an OFS system.

    Returns lon/lat bounding box that can be used to find CO-OPS stations,
    buoys, or other observation points within the model domain.

    Args:
        system_name: OFS system name (e.g. 'secofs', 'stofs_3d_atl').
    """
    reader = _get_reader(ctx)
    try:
        bounds = reader.get_domain_bounds(system_name)
    except ConfigError as e:
        return f"Error: {e}"

    if not bounds:
        return f"No domain bounds found in {system_name} config."

    return (
        f"## Domain Bounds: {system_name}\n\n"
        f"- **Longitude**: {bounds['lon_min']} to {bounds['lon_max']}\n"
        f"- **Latitude**: {bounds['lat_min']} to {bounds['lat_max']}\n\n"
        f"Use these bounds to find CO-OPS stations in the domain:\n"
        f"`coops_find_nearest_stations` with lat/lon within this range."
    )
