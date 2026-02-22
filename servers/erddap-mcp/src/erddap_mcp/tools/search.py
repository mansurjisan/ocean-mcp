"""Dataset discovery & search tools."""

from __future__ import annotations


from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import ERDDAPClient
from ..registry import DEFAULT_SERVER_URL, get_servers
from ..server import mcp
from ..utils import handle_erddap_error, parse_erddap_json


def _get_client(ctx: Context) -> ERDDAPClient:
    return ctx.request_context.lifespan_context["erddap_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def erddap_list_servers(
    ctx: Context,
    region: str | None = None,
    keyword: str | None = None,
) -> str:
    """List known ERDDAP servers from the built-in registry.

    Args:
        region: Filter by region (e.g., 'US East Coast', 'Pacific', 'Global').
        keyword: Filter by keyword matching name, focus, or region.
    """
    servers = get_servers(region=region, keyword=keyword)

    if not servers:
        return "No ERDDAP servers match the given filters. Try broader terms or omit filters to see all servers."

    lines = ["## Known ERDDAP Servers"]
    if region or keyword:
        filters = []
        if region:
            filters.append(f"Region: {region}")
        if keyword:
            filters.append(f"Keyword: {keyword}")
        lines.append(f"**Filters**: {', '.join(filters)}")
    lines.append("")

    lines.append("| Name | URL | Focus | Region |")
    lines.append("| --- | --- | --- | --- |")

    for s in servers:
        lines.append(f"| {s.name} | {s.url} | {s.focus} | {s.region} |")

    lines.append("")
    lines.append(
        f"*{len(servers)} servers listed. Use any server URL with other erddap tools.*"
    )

    return "\n".join(lines)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def erddap_search_datasets(
    ctx: Context,
    search_for: str,
    server_url: str = DEFAULT_SERVER_URL,
    protocol: str | None = None,
    items_per_page: int = 20,
    page: int = 1,
) -> str:
    """Search for datasets on an ERDDAP server using free-text search.

    Args:
        search_for: Search terms (e.g., 'sea surface temperature', 'chlorophyll', 'wind').
        server_url: ERDDAP server URL (default: CoastWatch West Coast).
        protocol: Filter by protocol — 'griddap' or 'tabledap' (optional).
        items_per_page: Number of results per page (default 20, max 1000).
        page: Page number for pagination (default 1).
    """
    try:
        client = _get_client(ctx)
        data = await client.search(
            server_url=server_url,
            search_for=search_for,
            page=page,
            items_per_page=items_per_page,
        )

        rows = parse_erddap_json(data)

        if not rows:
            return f"No datasets found for '{search_for}' on {server_url}. Try different search terms or a different server."

        # Filter by protocol if specified
        if protocol:
            if protocol == "griddap":
                rows = [r for r in rows if r.get("griddap", "") != ""]
            elif protocol == "tabledap":
                rows = [r for r in rows if r.get("tabledap", "") != ""]

        # Format results
        lines = ["## Dataset Search Results"]
        lines.append(f"**Server**: {server_url}")
        lines.append(f'**Search**: "{search_for}" | **Page**: {page}')
        lines.append("")

        lines.append("| Dataset ID | Title | Protocol |")
        lines.append("| --- | --- | --- |")

        for row in rows:
            dataset_id = row.get("Dataset ID", row.get("datasetID", ""))
            title = row.get("Title", row.get("title", ""))
            if len(title) > 80:
                title = title[:77] + "..."

            # Determine protocol
            proto = ""
            if row.get("griddap", ""):
                proto = "griddap"
            elif row.get("tabledap", ""):
                proto = "tabledap"

            lines.append(f"| {dataset_id} | {title} | {proto} |")

        lines.append("")
        lines.append(
            f"*{len(rows)} datasets found. Use erddap_get_dataset_info for details on a specific dataset.*"
        )
        if len(rows) == items_per_page:
            lines.append(f"*More results may be available — try page={page + 1}.*")

        return "\n".join(lines)

    except Exception as e:
        return handle_erddap_error(e, server_url)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def erddap_get_all_datasets(
    ctx: Context,
    server_url: str = DEFAULT_SERVER_URL,
    protocol: str | None = None,
    institution: str | None = None,
    search_text: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> str:
    """List all datasets available on a specific ERDDAP server.

    Args:
        server_url: ERDDAP server URL (default: CoastWatch West Coast).
        protocol: Filter by protocol — 'griddap' or 'tabledap' (optional).
        institution: Filter by institution name (optional, case-insensitive).
        search_text: Filter by text in title or summary (optional, case-insensitive).
        limit: Maximum number of datasets to return (default 50).
        offset: Number of datasets to skip for pagination (default 0).
    """
    try:
        client = _get_client(ctx)

        # Request key columns from allDatasets
        query = "datasetID,title,summary,institution,griddap,tabledap"
        data = await client.get_all_datasets(server_url=server_url, query=query)

        rows = parse_erddap_json(data)

        if not rows:
            return f"No datasets found on {server_url}."

        # Filter by protocol
        if protocol:
            if protocol == "griddap":
                rows = [r for r in rows if r.get("griddap", "") != ""]
            elif protocol == "tabledap":
                rows = [r for r in rows if r.get("tabledap", "") != ""]

        # Filter by institution
        if institution:
            inst_lower = institution.lower()
            rows = [
                r for r in rows if inst_lower in str(r.get("institution", "")).lower()
            ]

        # Filter by search text
        if search_text:
            text_lower = search_text.lower()
            rows = [
                r
                for r in rows
                if text_lower in str(r.get("title", "")).lower()
                or text_lower in str(r.get("summary", "")).lower()
            ]

        total = len(rows)
        rows = rows[offset : offset + limit]

        # Format output
        lines = [f"## All Datasets on {server_url}"]
        filters = []
        if protocol:
            filters.append(f"Protocol: {protocol}")
        if institution:
            filters.append(f"Institution: {institution}")
        if search_text:
            filters.append(f"Search: {search_text}")
        if filters:
            lines.append(f"**Filters**: {', '.join(filters)}")
        lines.append(
            f"**Showing**: {offset + 1}\u2013{offset + len(rows)} of {total} datasets"
        )
        lines.append("")

        lines.append("| Dataset ID | Title | Institution | Protocol |")
        lines.append("| --- | --- | --- | --- |")

        for row in rows:
            dataset_id = row.get("datasetID", "")
            title = str(row.get("title", ""))
            if len(title) > 60:
                title = title[:57] + "..."
            inst = str(row.get("institution", ""))
            if len(inst) > 30:
                inst = inst[:27] + "..."

            proto = ""
            if row.get("griddap", ""):
                proto = "griddap"
            elif row.get("tabledap", ""):
                proto = "tabledap"

            lines.append(f"| {dataset_id} | {title} | {inst} | {proto} |")

        lines.append("")
        lines.append(f"*{total} total datasets. Showing {len(rows)}.*")
        if offset + limit < total:
            lines.append(f"*Use offset={offset + limit} to see more.*")

        return "\n".join(lines)

    except Exception as e:
        return handle_erddap_error(e, server_url)
