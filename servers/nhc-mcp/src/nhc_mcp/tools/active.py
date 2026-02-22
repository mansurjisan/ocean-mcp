"""Tool: nhc_get_active_storms — currently active tropical cyclones."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import NHCClient
from ..server import mcp
from ..utils import format_tabular_data, handle_nhc_error


def _get_client(ctx: Context) -> NHCClient:
    return ctx.request_context.lifespan_context["nhc_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def nhc_get_active_storms(
    ctx: Context,
    response_format: str = "markdown",
) -> str:
    """Get currently active tropical cyclones from the National Hurricane Center.

    Returns a list of all active storms with their current classification,
    location, and advisory information. Returns an empty list outside of
    hurricane season or when no storms are active.

    Args:
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        storms = await client.get_active_storms()

        if not storms:
            return (
                "## Active Tropical Cyclones\n\n"
                "No active tropical cyclones at this time.\n\n"
                "*Tip: Use nhc_search_storms to search historical storms, or "
                "nhc_get_best_track to retrieve track data for past storms.*"
            )

        # Enrich storm data with classification
        rows = []
        for s in storms:
            row = {
                "name": s.get("name", "Unknown"),
                "classification": s.get("classification", ""),
                "id": s.get("id", ""),
                "binNumber": s.get("binNumber", ""),
                "movementDir": s.get("movementDir", ""),
                "movementSpeed": s.get("movementSpeed", ""),
                "pressure": s.get("pressure", ""),
                "wind": s.get("wind", ""),
                "lastUpdate": s.get("lastUpdate", ""),
                "advisory_url": s.get("publicAdvisory", {}).get("url", ""),
            }
            rows.append(row)

        if response_format == "json":
            import json

            return json.dumps({"active_storms": rows, "count": len(rows)}, indent=2)

        columns = [
            ("name", "Name"),
            ("classification", "Type"),
            ("id", "Storm ID"),
            ("wind", "Wind"),
            ("pressure", "Pressure"),
            ("movementDir", "Movement"),
            ("movementSpeed", "Speed"),
            ("lastUpdate", "Last Update"),
        ]

        return format_tabular_data(
            data=rows,
            columns=columns,
            title="Active Tropical Cyclones",
            count_label="active storms",
        )

    except Exception as e:
        return handle_nhc_error(e, "fetching active storms")
