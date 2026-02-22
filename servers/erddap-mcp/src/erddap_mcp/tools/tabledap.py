"""Tabular data access tools (tabledap)."""

from __future__ import annotations

import json

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import ERDDAPClient
from ..server import mcp
from ..utils import (
    build_tabledap_query,
    format_erddap_table,
    handle_erddap_error,
    parse_erddap_json,
)


def _get_client(ctx: Context) -> ERDDAPClient:
    return ctx.request_context.lifespan_context["erddap_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def erddap_get_tabledap_data(
    ctx: Context,
    server_url: str,
    dataset_id: str,
    variables: list[str] | None = None,
    constraints: dict[str, str | int | float] | None = None,
    limit: int = 1000,
    response_format: str = "markdown",
) -> str:
    """Retrieve tabular data from an ERDDAP tabledap dataset with constraint filtering.

    Args:
        server_url: ERDDAP server URL (e.g., 'https://coastwatch.pfeg.noaa.gov/erddap').
        dataset_id: ERDDAP dataset identifier.
        variables: List of variable names to retrieve (default: all).
        constraints: Dict of constraints, e.g. {"time>=": "2024-01-01", "latitude>=": 38.0, "station=": "46013"}.
        limit: Maximum number of rows to return (default 1000).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)

        # Warn if no constraints
        warnings: list[str] = []
        if not constraints:
            warnings.append(
                "No constraints specified — this may return a very large dataset. "
                "Consider using erddap_get_dataset_info first to understand available variables and time ranges, "
                'then add constraints like {"time>=": "2024-01-01"}.'
            )

        query = build_tabledap_query(
            variables=variables,
            constraints=constraints,
            limit=limit,
        )

        data = await client.get_tabledap(
            server_url=server_url,
            dataset_id=dataset_id,
            query=query,
        )

        rows = parse_erddap_json(data)

        if response_format == "json":
            result = {
                "server_url": server_url,
                "dataset_id": dataset_id,
                "record_count": len(rows),
                "data": rows,
            }
            if warnings:
                result["warnings"] = warnings
            return json.dumps(result, indent=2)

        # Markdown output
        table = data.get("table", {})
        columns = table.get("columnNames", [])
        units = table.get("columnUnits", [])

        # Build header with units
        display_columns = []
        for i, col in enumerate(columns):
            unit = units[i] if i < len(units) and units[i] else ""
            if unit and unit != "null":
                display_columns.append(f"{col} ({unit})")
            else:
                display_columns.append(col)

        lines: list[str] = []
        if warnings:
            for w in warnings:
                lines.append(f"**Warning**: {w}")
            lines.append("")

        title = f"Tabledap Data \u2014 {dataset_id}"
        meta = [f"Server: {server_url}"]
        if constraints:
            constraint_str = ", ".join(f"{k}{v}" for k, v in constraints.items())
            meta.append(f"Constraints: {constraint_str}")

        table_output = format_erddap_table(
            rows,
            columns=display_columns if display_columns else None,
            title=title,
            metadata_lines=meta,
            count_label="rows",
            max_rows=100,
        )

        lines.append(table_output)
        return "\n".join(lines)

    except Exception as e:
        return handle_erddap_error(e, server_url)
