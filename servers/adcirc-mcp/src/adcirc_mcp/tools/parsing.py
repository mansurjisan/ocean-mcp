"""File parsing tools — parse ADCIRC input files."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import ADCIRCClient
from ..server import mcp
from ..utils import parse_fort13, parse_fort14_header, parse_fort15, parse_fort22_header


def _get_client(ctx: Context) -> ADCIRCClient:
    return ctx.request_context.lifespan_context["adcirc_client"]


def _get_content(ctx: Context, file_path: str | None, content: str | None) -> str:
    """Get file content from either a file path or direct content."""
    if content:
        return content
    if file_path:
        client = _get_client(ctx)
        return client.read_file(file_path)
    raise ValueError("Either file_path or content must be provided.")


def _format_dict(data: dict, indent: int = 0) -> str:
    """Format a dict as readable text."""
    lines = []
    prefix = "  " * indent
    for key, value in data.items():
        if key.startswith("_"):
            continue
        if isinstance(value, dict):
            lines.append(f"{prefix}**{key}**:")
            lines.append(_format_dict(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}**{key}**: {len(value)} items")
            for item in value[:10]:  # Show first 10
                if isinstance(item, dict):
                    summary = ", ".join(f"{k}={v}" for k, v in item.items())
                    lines.append(f"{prefix}  - {summary}")
                else:
                    lines.append(f"{prefix}  - {item}")
            if len(value) > 10:
                lines.append(f"{prefix}  ... and {len(value) - 10} more")
        else:
            lines.append(f"{prefix}**{key}**: {value}")
    return "\n".join(lines)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def adcirc_parse_fort15(
    ctx: Context,
    file_path: str | None = None,
    content: str | None = None,
) -> str:
    """Parse an ADCIRC fort.15 control file into a structured summary.

    Extracts run parameters, timestep, forcing configuration, tidal
    constituents, output settings, and station locations.

    Args:
        file_path: Path to the fort.15 file on disk.
        content: Raw text content of the fort.15 file (alternative to file_path).
    """
    try:
        text = _get_content(ctx, file_path, content)
        parsed = parse_fort15(text)

        lines = ["## Fort.15 Configuration Summary"]
        source = file_path if file_path else "provided content"
        lines.append(f"*Source: {source}*\n")

        # Key parameters
        lines.append("### Run Info")
        lines.append(f"- **Description**: {parsed.get('RUNDES', 'N/A')}")
        lines.append(f"- **Run ID**: {parsed.get('RUNID', 'N/A')}")
        lines.append(f"- **Hot start**: IHOT={parsed.get('IHOT', 'N/A')}")

        lines.append("\n### Time Stepping")
        lines.append(f"- **Timestep (DTDP)**: {parsed.get('DTDP', 'N/A')} seconds")
        lines.append(f"- **Duration (RNDAY)**: {parsed.get('RNDAY', 'N/A')} days")
        lines.append(f"- **Start time (STATIM)**: {parsed.get('STATIM', 'N/A')} days")
        lines.append(f"- **Ramp duration (DRAMP)**: {parsed.get('DRAMP', 'N/A')} days")

        lines.append("\n### Physics")
        lines.append(f"- **Coordinate system (ICS)**: {parsed.get('ICS', 'N/A')}")
        lines.append(f"- **Model type (IM)**: {parsed.get('IM', 'N/A')}")
        lines.append(f"- **Friction (NOLIBF)**: {parsed.get('NOLIBF', 'N/A')}")
        lines.append(f"- **Wetting/drying (NOLIFA)**: {parsed.get('NOLIFA', 'N/A')}")
        lines.append(f"- **Met forcing (NWS)**: {parsed.get('NWS', 'N/A')}")
        lines.append(f"- **Coriolis (NCOR)**: {parsed.get('NCOR', 'N/A')}")

        lines.append("\n### Tidal Forcing")
        lines.append(
            f"- **Tidal potential constituents (NTIF)**: {parsed.get('NTIF', 0)}"
        )
        for tp in parsed.get("tidal_potential", []):
            lines.append(f"  - {tp.get('name', '?')}")
        lines.append(
            f"- **Boundary forcing frequencies (NBFR)**: {parsed.get('NBFR', 0)}"
        )
        for bf in parsed.get("boundary_forcing", []):
            lines.append(f"  - {bf.get('name', '?')}")

        lines.append("\n### Nodal Attributes")
        lines.append(f"- **Count (NWP)**: {parsed.get('NWP', 0)}")
        for attr in parsed.get("nodal_attributes", []):
            lines.append(f"  - {attr}")

        if parsed.get("NSTAE", 0) > 0:
            lines.append(f"\n### Elevation Stations: {parsed.get('NSTAE', 0)}")

        # Warnings from parser
        warnings = parsed.get("_warnings", [])
        if warnings:
            lines.append("\n### Parser Warnings")
            for w in warnings:
                lines.append(f"- {w}")

        lines.append(
            f"\n*Parsed {parsed.get('_parsed_lines', 0)} of {parsed.get('_raw_lines', 0)} lines*"
        )

        return "\n".join(lines)
    except Exception as e:
        return f"Error parsing fort.15: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def adcirc_parse_fort14(
    ctx: Context,
    file_path: str | None = None,
    content: str | None = None,
) -> str:
    """Parse an ADCIRC fort.14 mesh file header (NOT the full mesh).

    Returns grid name, node count, element count, and boundary information.
    Does NOT load node coordinates or element connectivity into memory.

    Args:
        file_path: Path to the fort.14 file on disk.
        content: Raw text content (or header portion) of the fort.14 file.
    """
    try:
        if content:
            text = content
        elif file_path:
            client = _get_client(ctx)
            text = client.read_file_header(file_path, max_lines=50)
        else:
            return "Error: Either file_path or content must be provided."

        parsed = parse_fort14_header(text)

        if "error" in parsed:
            return f"Error: {parsed['error']}"

        lines = ["## Fort.14 Mesh Summary"]
        if file_path:
            lines.append(f"*Source: {file_path}*\n")
        lines.append(f"- **Grid name**: {parsed.get('grid_name', 'N/A')}")
        lines.append(f"- **Nodes**: {parsed.get('num_nodes', 'N/A'):,}")
        lines.append(f"- **Elements**: {parsed.get('num_elements', 'N/A'):,}")
        if "num_open_boundaries" in parsed:
            lines.append(f"- **Open boundaries**: {parsed['num_open_boundaries']}")
        if "total_open_boundary_nodes" in parsed:
            lines.append(
                f"- **Total open boundary nodes**: {parsed['total_open_boundary_nodes']}"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"Error parsing fort.14: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def adcirc_parse_fort13(
    ctx: Context,
    file_path: str | None = None,
    content: str | None = None,
) -> str:
    """Parse an ADCIRC fort.13 nodal attributes file.

    Returns attribute names, default values, and non-default node counts.

    Args:
        file_path: Path to the fort.13 file on disk.
        content: Raw text content of the fort.13 file.
    """
    try:
        text = _get_content(ctx, file_path, content)
        parsed = parse_fort13(text)

        if "error" in parsed:
            return f"Error: {parsed['error']}"

        lines = ["## Fort.13 Nodal Attributes"]
        if file_path:
            lines.append(f"*Source: {file_path}*\n")
        lines.append(f"- **Grid name**: {parsed.get('grid_name', 'N/A')}")
        lines.append(f"- **Nodes**: {parsed.get('num_nodes', 'N/A'):,}")
        lines.append(f"- **Attributes**: {parsed.get('num_attributes', 0)}")

        lines.append("\n### Attribute Details")
        for attr in parsed.get("attributes", []):
            name = attr.get("name", "?")
            vals = attr.get("values_per_node", "?")
            default = attr.get("default_values", "?")
            nondefault = attr.get("num_nondefault_nodes", "?")
            lines.append(
                f"- **{name}**: {vals} val/node, default={default}, non-default nodes={nondefault}"
            )

        return "\n".join(lines)
    except Exception as e:
        return f"Error parsing fort.13: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def adcirc_parse_fort22(
    ctx: Context,
    nws: int = 0,
    file_path: str | None = None,
    content: str | None = None,
) -> str:
    """Parse an ADCIRC fort.22 meteorological forcing file header.

    Returns format type, time range, and spatial extent based on the NWS value.

    Args:
        nws: NWS value from fort.15 (determines the file format).
        file_path: Path to the fort.22 file on disk.
        content: Raw text content of the fort.22 file.
    """
    try:
        text = _get_content(ctx, file_path, content)
        parsed = parse_fort22_header(text, nws)

        if "error" in parsed:
            return f"Error: {parsed['error']}"

        lines = ["## Fort.22 Meteorological Forcing"]
        if file_path:
            lines.append(f"*Source: {file_path}*\n")
        lines.append(f"- **NWS**: {nws}")
        lines.append(f"- **Format**: {parsed.get('format', 'unknown')}")
        lines.append(f"- **Lines**: {parsed.get('num_lines', 'N/A')}")

        if "num_records" in parsed:
            lines.append(f"- **Records**: {parsed['num_records']}")
        if "first_timestamp" in parsed:
            lines.append(f"- **First timestamp**: {parsed['first_timestamp']}")
        if "last_timestamp" in parsed:
            lines.append(f"- **Last timestamp**: {parsed['last_timestamp']}")
        if "header_line" in parsed:
            lines.append(f"- **Header**: {parsed['header_line']}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error parsing fort.22: {e}"
