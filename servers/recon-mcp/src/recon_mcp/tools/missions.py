"""Tool: recon_list_missions — list reconnaissance data files from the NHC archive."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import ReconClient
from ..server import mcp
from ..utils import (
    format_json_response,
    format_tabular_data,
    handle_recon_error,
    parse_directory_listing,
)


def _get_client(ctx: Context) -> ReconClient:
    return ctx.request_context.lifespan_context["recon_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def recon_list_missions(
    ctx: Context,
    year: int,
    product: str,
    basin: str = "al",
    month: int | None = None,
    day: int | None = None,
    limit: int = 50,
    response_format: str = "markdown",
) -> str:
    """List available reconnaissance data files from the NHC archive.

    Browse the NHC reconnaissance archive directory for HDOB, VDM, or
    dropsonde bulletins. Use this to discover what data files exist
    before fetching specific observations.

    Args:
        year: Year to search (e.g., 2024).
        product: Data product type — 'hdob', 'vdm', or 'dropsonde'.
        basin: Basin — 'al' (Atlantic, default), 'ep' (East Pacific), or 'cp' (Central Pacific).
        month: Optional month filter (1-12) to narrow results by filename date.
        day: Optional day filter (1-31) to narrow results by filename date.
        limit: Maximum number of files to return (default 50).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        url = client.build_archive_dir_url(year, product, basin)
        html = await client.list_directory(url)
        entries = parse_directory_listing(html)

        # Apply date filters on filenames
        if month is not None:
            month_str = f"{month:02d}"
            # Filenames often contain YYYYMMDD — filter by month digits
            entries = [
                e
                for e in entries
                if _filename_matches_date(e["filename"], year, month_str, None)
            ]

        if day is not None:
            day_str = f"{day:02d}"
            month_str = f"{month:02d}" if month is not None else None
            entries = [
                e
                for e in entries
                if _filename_matches_date(e["filename"], year, month_str, day_str)
            ]

        # Sort by filename (reverse for most recent first)
        entries.sort(key=lambda e: e["filename"], reverse=True)

        # Apply limit
        entries = entries[:limit]

        if not entries:
            return (
                f"## Reconnaissance Archive Listing\n\n"
                f"No {product.upper()} files found for {year} in the "
                f"{basin.upper()} basin"
                f"{f' for month {month}' if month else ''}"
                f"{f' day {day}' if day else ''}.\n\n"
                f"*Archive URL: {url}*"
            )

        if response_format == "json":
            return format_json_response(
                entries,
                context=f"{product.upper()} files for {year}, basin={basin.upper()}",
            )

        columns = [
            ("filename", "Filename"),
            ("href", "Path"),
        ]

        metadata = [
            f"Year: {year}",
            f"Product: {product.upper()}",
            f"Basin: {basin.upper()}",
        ]
        if month:
            metadata.append(f"Month: {month:02d}")
        if day:
            metadata.append(f"Day: {day:02d}")

        return format_tabular_data(
            data=entries,
            columns=columns,
            title=f"Reconnaissance Archive — {product.upper()} Files",
            metadata_lines=metadata,
            count_label="files",
        )

    except Exception as e:
        return handle_recon_error(e, f"listing {product} missions for {year}")


def _filename_matches_date(
    filename: str, year: int, month_str: str | None, day_str: str | None
) -> bool:
    """Check if a filename contains a date matching the given filter."""
    # Look for YYYYMMDD pattern in filename
    if month_str and day_str:
        pattern = f"{year}{month_str}{day_str}"
    elif month_str:
        pattern = f"{year}{month_str}"
    else:
        return True

    return pattern in filename
