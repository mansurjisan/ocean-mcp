"""File parsing tools — parse SCHISM input files."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import SchismClient
from ..server import mcp
from ..utils import parse_bctides, parse_hgrid_header, parse_param_nml, parse_vgrid


def _get_client(ctx: Context) -> SchismClient:
    return ctx.request_context.lifespan_context["schism_client"]


def _get_content(ctx: Context, file_path: str | None, content: str | None) -> str:
    """Get file content from either a file path or direct content."""
    if content:
        return content
    if file_path:
        client = _get_client(ctx)
        return client.read_file(file_path)
    raise ValueError("Either file_path or content must be provided.")


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def schism_parse_param_nml(
    ctx: Context,
    file_path: str | None = None,
    content: str | None = None,
) -> str:
    """Parse a SCHISM param.nml FORTRAN namelist file.

    Returns all parameters organized by section with annotations.

    Args:
        file_path: Path to the param.nml file on disk.
        content: Raw text content of param.nml (alternative to file_path).
    """
    try:
        text = _get_content(ctx, file_path, content)
        parsed = parse_param_nml(text)
        sections = parsed.get("_sections", {})

        lines = ["## param.nml Configuration Summary"]
        source = file_path if file_path else "provided content"
        lines.append(f"*Source: {source}*\n")

        # Key parameters summary
        lines.append("### Key Parameters")
        dt = parsed.get("dt", "not set")
        lines.append(f"- **dt**: {dt} seconds")
        lines.append(f"- **rnday**: {parsed.get('rnday', 'not set')} days")
        lines.append(f"- **nhot**: {parsed.get('nhot', 0)}")
        lines.append(f"- **ics**: {parsed.get('ics', 'not set')}")
        lines.append(f"- **nws**: {parsed.get('nws', 0)}")
        lines.append(f"- **nspool**: {parsed.get('nspool', 'not set')}")
        lines.append(f"- **ihfskip**: {parsed.get('ihfskip', 'not set')}")

        # All sections
        for sect_name in ["CORE", "OPT", "SCHOUT"]:
            if sect_name in sections:
                lines.append(f"\n### &{sect_name}")
                for key, value in sections[sect_name].items():
                    lines.append(f"- **{key}** = {value}")

        # Any other sections
        for sect_name, params in sections.items():
            if sect_name not in ("CORE", "OPT", "SCHOUT"):
                lines.append(f"\n### &{sect_name}")
                for key, value in params.items():
                    lines.append(f"- **{key}** = {value}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error parsing param.nml: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def schism_parse_hgrid(
    ctx: Context,
    file_path: str | None = None,
    content: str | None = None,
) -> str:
    """Parse a SCHISM hgrid.gr3 horizontal grid file header.

    Returns node/element counts, bounding box, and boundary info.
    Does NOT load full mesh into memory.

    Args:
        file_path: Path to the hgrid.gr3 file on disk.
        content: Raw text content (or header portion) of hgrid.gr3.
    """
    try:
        if content:
            text = content
        elif file_path:
            client = _get_client(ctx)
            text = client.read_file_header(file_path, max_lines=200)
        else:
            return "Error: Either file_path or content must be provided."

        parsed = parse_hgrid_header(text)

        if "error" in parsed:
            return f"Error: {parsed['error']}"

        lines = ["## hgrid.gr3 Mesh Summary"]
        if file_path:
            lines.append(f"*Source: {file_path}*\n")
        lines.append(f"- **Grid name**: {parsed.get('grid_name', 'N/A')}")
        lines.append(f"- **Nodes**: {parsed.get('num_nodes', 'N/A'):,}")
        lines.append(f"- **Elements**: {parsed.get('num_elements', 'N/A'):,}")

        if "bounding_box" in parsed:
            bb = parsed["bounding_box"]
            lines.append(
                f"- **Bounding box**: ({bb['min_x']}, {bb['min_y']}) to ({bb['max_x']}, {bb['max_y']})"
            )
        if "max_depth" in parsed:
            lines.append(f"- **Max depth**: {parsed['max_depth']} m")
        if "num_open_boundaries" in parsed:
            lines.append(f"- **Open boundaries**: {parsed['num_open_boundaries']}")
        if "total_open_boundary_nodes" in parsed:
            lines.append(
                f"- **Total open boundary nodes**: {parsed['total_open_boundary_nodes']}"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"Error parsing hgrid.gr3: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def schism_parse_vgrid(
    ctx: Context,
    file_path: str | None = None,
    content: str | None = None,
) -> str:
    """Parse a SCHISM vgrid.in vertical grid file.

    Returns grid type (LSC2/SZ), number of levels, and layer distribution.

    Args:
        file_path: Path to the vgrid.in file on disk.
        content: Raw text content of vgrid.in.
    """
    try:
        text = _get_content(ctx, file_path, content)
        parsed = parse_vgrid(text)

        if "error" in parsed:
            return f"Error: {parsed['error']}"

        lines = ["## vgrid.in Vertical Grid Summary"]
        if file_path:
            lines.append(f"*Source: {file_path}*\n")
        lines.append(
            f"- **Type**: {parsed.get('type_name', 'unknown')} (ivcor={parsed.get('ivcor', '?')})"
        )
        if "type_description" in parsed:
            lines.append(f"- **Description**: {parsed['type_description']}")
        lines.append(f"- **Total levels (nvrt)**: {parsed.get('nvrt', 'N/A')}")

        if parsed.get("ivcor") == 2:
            lines.append(f"- **Z-levels (kz)**: {parsed.get('kz', 'N/A')}")
            lines.append(
                f"- **S-Z transition depth (h_s)**: {parsed.get('h_s', 'N/A')} m"
            )

        lines.append(f"- **File lines**: {parsed.get('num_lines', 'N/A')}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error parsing vgrid.in: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def schism_parse_bctides(
    ctx: Context,
    file_path: str | None = None,
    content: str | None = None,
) -> str:
    """Parse a SCHISM bctides.in tidal boundary condition file.

    Returns tidal constituent names/frequencies, boundary segment types,
    and node counts.

    Args:
        file_path: Path to the bctides.in file on disk.
        content: Raw text content of bctides.in.
    """
    try:
        text = _get_content(ctx, file_path, content)
        parsed = parse_bctides(text)

        if "error" in parsed:
            return f"Error: {parsed['error']}"

        lines = ["## bctides.in Summary"]
        if file_path:
            lines.append(f"*Source: {file_path}*\n")
        lines.append(f"- **Tidal frequencies (nbfr)**: {parsed.get('nbfr', 0)}")

        if parsed.get("constituents"):
            lines.append("\n### Tidal Constituents")
            for c in parsed["constituents"]:
                freq = c.get("frequency", "?")
                lines.append(f"- **{c['name']}**: frequency={freq}")

        if parsed.get("num_open_boundaries"):
            lines.append(f"\n- **Open boundaries**: {parsed['num_open_boundaries']}")

        if parsed.get("boundaries"):
            lines.append("\n### Boundary Segments")
            from ..models import BC_TYPES

            for i, b in enumerate(parsed["boundaries"], 1):
                nodes = b.get("num_nodes", "?")
                elev_type = b.get("elevation_type", "?")
                flux_type = b.get("flux_type", "?")
                elev_desc = (
                    BC_TYPES.get(elev_type, {}).get("name", "unknown")
                    if isinstance(elev_type, int)
                    else "?"
                )
                lines.append(
                    f"- **Boundary {i}**: {nodes} nodes, "
                    f"elevation={elev_type} ({elev_desc}), "
                    f"flux={flux_type}"
                )

        return "\n".join(lines)
    except Exception as e:
        return f"Error parsing bctides.in: {e}"
