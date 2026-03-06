"""Image retrieval tools for GOES satellite imagery."""

import json

from mcp.server.fastmcp import Context
from mcp.server.fastmcp.utilities.types import Image
from mcp.types import ToolAnnotations

from ..client import GOESClient
from ..models import (
    COVERAGES,
    PRODUCTS,
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
        openWorldHint=True,
    )
)
async def goes_get_latest_image(
    ctx: Context,
    satellite: str = "goes-19",
    coverage: str = "CONUS",
    product: str = "GEOCOLOR",
    resolution: str = "1250x750",
    response_format: str = "image",
):
    """Get the most recent GOES satellite image.

    Fetches the latest image from NOAA STAR CDN. Default returns the image
    directly (base64 JPEG). Use response_format='markdown' for a URL reference
    or 'json' for metadata only.

    Args:
        satellite: Satellite — 'goes-19' (East) or 'goes-18' (West).
        coverage: Coverage area — 'CONUS' (Continental US) or 'FD' (Full Disk).
        product: Product — band number ('01'-'16') or composite ('GEOCOLOR', 'AirMass', 'Sandwich', 'FireTemperature', 'Dust', 'DMW').
        resolution: Image resolution — 'thumbnail', '625x375', '1250x750', '2500x1500', '5000x3000', 'latest'.
        response_format: Output — 'image' (default, embedded JPEG), 'markdown' (URL), or 'json' (metadata).
    """
    try:
        client = _get_client(ctx)
        url = client.build_latest_url(satellite, coverage, product, resolution)
        sat_info = SATELLITES.get(satellite.lower(), {})
        product_info = PRODUCTS.get(product, {})
        product_name = product_info.get("name", product)

        if response_format == "json":
            return json.dumps(
                {
                    "url": url,
                    "satellite": satellite,
                    "satellite_name": sat_info.get("name", satellite),
                    "coverage": coverage,
                    "product": product,
                    "product_name": product_name,
                    "resolution": resolution,
                },
                indent=2,
            )

        if response_format == "markdown":
            lines = [
                f"## Latest {product_name} — {sat_info.get('name', satellite)}",
                "",
                f"![{product_name}]({url})",
                "",
                f"- **Satellite**: {sat_info.get('name', satellite)}",
                f"- **Coverage**: {coverage}",
                f"- **Product**: {product_name} ({product})",
                f"- **Resolution**: {resolution}",
                f"- **URL**: {url}",
            ]
            return "\n".join(lines)

        # Default: return embedded image
        img_bytes = await client.get_image(url)
        return Image(data=img_bytes, format="jpeg")

    except Exception as e:
        return f"**Error**: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def goes_get_image(
    ctx: Context,
    timestamp: str,
    satellite: str = "goes-19",
    coverage: str = "CONUS",
    product: str = "GEOCOLOR",
    resolution: str = "1250x750",
    response_format: str = "image",
):
    """Get a GOES satellite image for a specific timestamp.

    Use goes_get_available_times to find valid timestamps first.
    Timestamp format is YYYYDDDHHmm (DDD = day-of-year).

    Args:
        timestamp: Image timestamp in YYYYDDDHHmm format (11 digits). Use goes_get_available_times to discover valid timestamps.
        satellite: Satellite — 'goes-19' (East) or 'goes-18' (West).
        coverage: Coverage area — 'CONUS' (Continental US) or 'FD' (Full Disk).
        product: Product — band number ('01'-'16') or composite ('GEOCOLOR', 'AirMass', etc.).
        resolution: Image resolution — 'thumbnail', '625x375', '1250x750', '2500x1500', '5000x3000'.
        response_format: Output — 'image' (default, embedded JPEG), 'markdown' (URL), or 'json' (metadata).
    """
    try:
        client = _get_client(ctx)
        url = client.build_timestamped_url(
            satellite, coverage, product, timestamp, resolution
        )
        sat_info = SATELLITES.get(satellite.lower(), {})
        product_info = PRODUCTS.get(product, {})
        product_name = product_info.get("name", product)

        if response_format == "json":
            return json.dumps(
                {
                    "url": url,
                    "satellite": satellite,
                    "satellite_name": sat_info.get("name", satellite),
                    "coverage": coverage,
                    "product": product,
                    "product_name": product_name,
                    "timestamp": timestamp,
                    "resolution": resolution,
                },
                indent=2,
            )

        if response_format == "markdown":
            lines = [
                f"## {product_name} — {sat_info.get('name', satellite)} @ {timestamp}",
                "",
                f"![{product_name}]({url})",
                "",
                f"- **Satellite**: {sat_info.get('name', satellite)}",
                f"- **Coverage**: {coverage}",
                f"- **Product**: {product_name} ({product})",
                f"- **Timestamp**: {timestamp}",
                f"- **Resolution**: {resolution}",
                f"- **URL**: {url}",
            ]
            return "\n".join(lines)

        # Default: return embedded image
        img_bytes = await client.get_image(url)
        return Image(data=img_bytes, format="jpeg")

    except Exception as e:
        return f"**Error**: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def goes_get_sector_image(
    ctx: Context,
    sector: str = "se",
    satellite: str = "goes-19",
    product: str = "GEOCOLOR",
    resolution: str = "1250x750",
    response_format: str = "image",
):
    """Get latest GOES imagery for a regional sector.

    Sectors provide zoomed-in views of specific regions. Available sectors:
    'se' (Southeast), 'ne' (Northeast), 'car' (Caribbean),
    'taw' (Tropical Atlantic Wide), 'pr' (Puerto Rico).

    Args:
        sector: Regional sector — 'se', 'ne', 'car', 'taw', 'pr'.
        satellite: Satellite — 'goes-19' (East) or 'goes-18' (West).
        product: Product — band number ('01'-'16') or composite ('GEOCOLOR', 'AirMass', etc.).
        resolution: Image resolution — 'thumbnail', '625x375', '1250x750', '2500x1500', '5000x3000', 'latest'.
        response_format: Output — 'image' (default, embedded JPEG), 'markdown' (URL), or 'json' (metadata).
    """
    try:
        client = _get_client(ctx)
        url = client.build_sector_url(satellite, sector, product, resolution)
        sat_info = SATELLITES.get(satellite.lower(), {})
        sector_info = SECTORS.get(sector.lower(), {})
        product_info = PRODUCTS.get(product, {})
        product_name = product_info.get("name", product)
        sector_name = sector_info.get("name", sector)

        if response_format == "json":
            return json.dumps(
                {
                    "url": url,
                    "satellite": satellite,
                    "satellite_name": sat_info.get("name", satellite),
                    "sector": sector,
                    "sector_name": sector_name,
                    "product": product,
                    "product_name": product_name,
                    "resolution": resolution,
                },
                indent=2,
            )

        if response_format == "markdown":
            lines = [
                f"## Latest {product_name} — {sector_name} ({sat_info.get('name', satellite)})",
                "",
                f"![{product_name} - {sector_name}]({url})",
                "",
                f"- **Satellite**: {sat_info.get('name', satellite)}",
                f"- **Sector**: {sector_name} ({sector})",
                f"- **Product**: {product_name} ({product})",
                f"- **Resolution**: {resolution}",
                f"- **URL**: {url}",
            ]
            return "\n".join(lines)

        # Default: return embedded image
        img_bytes = await client.get_image(url)
        return Image(data=img_bytes, format="jpeg")

    except Exception as e:
        return f"**Error**: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def goes_get_current_view(
    ctx: Context,
    satellite: str = "goes-19",
    response_format: str = "markdown",
) -> str:
    """Quick overview of what GOES satellite imagery is available now.

    Shows the latest available timestamp for key coverage/product combinations,
    giving a snapshot of current data availability.

    Args:
        satellite: Satellite — 'goes-19' (East) or 'goes-18' (West).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        sat_info = SATELLITES.get(satellite.lower(), {})

        # Check a few key products across coverages
        checks = [
            ("CONUS", "GEOCOLOR"),
            ("CONUS", "13"),
            ("FD", "GEOCOLOR"),
        ]

        results = []
        for sector, product in checks:
            try:
                timestamps = await client.get_slider_times(
                    satellite=satellite,
                    sector=sector,
                    product=product,
                    limit=1,
                )
                latest = timestamps[0] if timestamps else "N/A"
                results.append(
                    {
                        "coverage": sector,
                        "product": product,
                        "product_name": PRODUCTS.get(product, {}).get("name", product),
                        "latest_time": latest,
                    }
                )
            except Exception:
                results.append(
                    {
                        "coverage": sector,
                        "product": product,
                        "product_name": PRODUCTS.get(product, {}).get("name", product),
                        "latest_time": "unavailable",
                    }
                )

        if response_format == "json":
            return json.dumps(
                {
                    "satellite": satellite,
                    "satellite_name": sat_info.get("name", satellite),
                    "availability": results,
                },
                indent=2,
            )

        lines: list[str] = []
        lines.append(f"## Current GOES Imagery — {sat_info.get('name', satellite)}\n")
        lines.append("| Coverage | Product | Latest Available (UTC) |")
        lines.append("|----------|---------|----------------------|")

        for r in results:
            ts = r["latest_time"]
            if ts not in ("N/A", "unavailable") and len(ts) >= 14:
                formatted = (
                    f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[8:10]}:{ts[10:12]}:{ts[12:14]}"
                )
            else:
                formatted = ts
            lines.append(
                f"| {r['coverage']} | {r['product_name']} ({r['product']}) | {formatted} |"
            )

        lines.append("")
        lines.append("### Available Coverages")
        for code, cov in COVERAGES.items():
            lines.append(f"- **{code}**: {cov['name']}")
        lines.append("")
        lines.append("### Available Sectors")
        for code, sec in SECTORS.items():
            lines.append(f"- **{code}**: {sec['name']}")
        lines.append("")
        lines.append("### Popular Products")
        for prod_id in ("GEOCOLOR", "AirMass", "Sandwich", "13", "08"):
            info = PRODUCTS.get(prod_id, {})
            lines.append(
                f"- **{prod_id}**: {info.get('name', prod_id)} — {info.get('description', '')}"
            )

        return "\n".join(lines)

    except Exception as e:
        return f"**Error**: {e}"
