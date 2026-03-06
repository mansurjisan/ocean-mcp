"""Discovery tools for GOES satellite imagery products and timestamps."""

import json

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import GOESClient
from ..models import (
    ABI_BANDS,
    COMPOSITE_PRODUCTS,
    COVERAGES,
    RESOLUTIONS,
    SATELLITES,
    SECTORS,
)
from ..server import mcp


def _get_client(ctx: Context) -> GOESClient:
    """Extract the GOESClient from the MCP lifespan context."""
    return ctx.request_context.lifespan_context["goes_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def goes_list_products(
    ctx: Context,
    response_format: str = "markdown",
) -> str:
    """List all available GOES satellite imagery products.

    Returns a catalog of ABI bands (1-16) and composite products (GeoColor,
    AirMass, etc.) with wavelength, type, and description for each.

    Args:
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    if response_format == "json":
        result = {
            "satellites": SATELLITES,
            "bands": ABI_BANDS,
            "composites": COMPOSITE_PRODUCTS,
            "coverages": {k: v["name"] for k, v in COVERAGES.items()},
            "sectors": {k: v["name"] for k, v in SECTORS.items()},
            "resolutions": {k: v["pixels"] for k, v in RESOLUTIONS.items()},
        }
        return json.dumps(result, indent=2)

    lines: list[str] = []

    # Satellites
    lines.append("## GOES Satellites\n")
    for key, sat in SATELLITES.items():
        lines.append(
            f"- **{sat['name']}** (`{key}`) — {sat['position']} — {sat['description']}"
        )
    lines.append("")

    # ABI Bands
    lines.append("## ABI Bands\n")
    lines.append("| Band | Name | Wavelength | Type | Description |")
    lines.append("|------|------|-----------|------|-------------|")
    for band_id, band in ABI_BANDS.items():
        lines.append(
            f"| {band_id} | {band['name']} | {band['wavelength']} | "
            f"{band['type']} | {band['description']} |"
        )
    lines.append("")

    # Composites
    lines.append("## Composite Products\n")
    lines.append("| Product | Name | Description |")
    lines.append("|---------|------|-------------|")
    for prod_id, prod in COMPOSITE_PRODUCTS.items():
        lines.append(f"| {prod_id} | {prod['name']} | {prod['description']} |")
    lines.append("")

    # Coverages
    lines.append("## Coverages\n")
    for code, cov in COVERAGES.items():
        lines.append(f"- **{code}** — {cov['name']}: {cov['description']}")
    lines.append("")

    # Sectors
    lines.append("## Sectors\n")
    for code, sec in SECTORS.items():
        lines.append(f"- **{code}** — {sec['name']}: {sec['description']}")
    lines.append("")

    # Resolutions
    lines.append("## Resolutions\n")
    lines.append("| Key | Pixels | Approx Size |")
    lines.append("|-----|--------|-------------|")
    for key, res in RESOLUTIONS.items():
        lines.append(f"| {key} | {res['pixels']} | {res['approx_size']} |")

    return "\n".join(lines)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def goes_get_available_times(
    ctx: Context,
    satellite: str = "goes-19",
    sector: str = "CONUS",
    product: str = "GEOCOLOR",
    limit: int = 10,
    response_format: str = "markdown",
) -> str:
    """Get available image timestamps for a GOES product.

    Queries the RAMMB/CIRA SLIDER API for the most recent image times.
    Use these timestamps with goes_get_image to fetch historical images.

    Args:
        satellite: Satellite — 'goes-19' (East) or 'goes-18' (West).
        sector: Coverage or sector code — 'CONUS', 'FD', 'se', 'ne', 'car', 'taw', 'pr'.
        product: Product code — band number ('01'-'16') or composite name ('GEOCOLOR', 'AirMass', etc.).
        limit: Maximum number of timestamps to return (default 10, max 100).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        limit = min(max(1, limit), 100)
        timestamps = await client.get_slider_times(
            satellite=satellite,
            sector=sector,
            product=product,
            limit=limit,
        )

        if response_format == "json":
            return json.dumps(
                {
                    "satellite": satellite,
                    "sector": sector,
                    "product": product,
                    "count": len(timestamps),
                    "timestamps": timestamps,
                },
                indent=2,
            )

        lines: list[str] = []
        lines.append(
            f"## Available Times — {product} ({satellite.upper()}, {sector})\n"
        )

        if not timestamps:
            lines.append("No timestamps available for this combination.")
            return "\n".join(lines)

        lines.append(
            f"Found **{len(timestamps)}** available times (most recent first):\n"
        )
        lines.append("| # | Timestamp (UTC) |")
        lines.append("|---|----------------|")
        for i, ts in enumerate(timestamps, 1):
            # Format YYYYMMDDHHmmss → YYYY-MM-DD HH:mm:ss
            if len(ts) >= 14:
                formatted = (
                    f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[8:10]}:{ts[10:12]}:{ts[12:14]}"
                )
            else:
                formatted = ts
            lines.append(f"| {i} | {formatted} |")

        lines.append(
            "\n*Use these timestamps with `goes_get_image` to fetch specific images.*"
        )
        return "\n".join(lines)

    except Exception as e:
        return f"**Error**: {e}"
