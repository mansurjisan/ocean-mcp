"""Documentation fetching tools — access ADCIRC wiki."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import ADCIRCClient, ADCIRCClientError
from ..models import ADCIRC_WIKI_BASE
from ..server import mcp


def _get_client(ctx: Context) -> ADCIRCClient:
    return ctx.request_context.lifespan_context["adcirc_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def adcirc_fetch_docs(
    ctx: Context,
    topic: str,
) -> str:
    """Fetch documentation from the ADCIRC wiki for a specific topic.

    Retrieves the wiki page content as plain text.

    Args:
        topic: Wiki page title or topic (e.g., 'Fort.15', 'NWS', 'Hot Start').
    """
    try:
        client = _get_client(ctx)
        content = await client.fetch_wiki_page(topic)

        if not content:
            return f"No content found for topic '{topic}'. Try `adcirc_search_docs` to find related pages."

        # Truncate if too long
        max_length = 4000
        if len(content) > max_length:
            content = (
                content[:max_length]
                + f"\n\n... (truncated, full page at {ADCIRC_WIKI_BASE}/wiki/{topic.replace(' ', '_')})"
            )

        lines = [f"## ADCIRC Wiki: {topic}"]
        lines.append(f"*Source: {ADCIRC_WIKI_BASE}/wiki/{topic.replace(' ', '_')}*\n")
        lines.append(content)

        return "\n".join(lines)
    except ADCIRCClientError as e:
        return (
            f"Wiki error: {e}. Try `adcirc_search_docs` to find the correct page title."
        )
    except Exception as e:
        return f"Error fetching documentation: {e}"


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def adcirc_search_docs(
    ctx: Context,
    query: str,
    limit: int = 10,
) -> str:
    """Search the ADCIRC wiki and return matching pages with summaries.

    Args:
        query: Search terms (e.g., 'tidal forcing', 'hot start', 'wetting drying').
        limit: Maximum number of results to return (default 10).
    """
    try:
        client = _get_client(ctx)
        results = await client.search_wiki(query, limit=limit)

        if not results:
            return f"No results found for '{query}'. Try different search terms or check the ADCIRC wiki directly at {ADCIRC_WIKI_BASE}."

        lines = [f"## ADCIRC Wiki Search: '{query}'"]
        lines.append(f"*{len(results)} results found*\n")

        for r in results:
            lines.append(f"### [{r['title']}]({r['url']})")
            if r.get("snippet"):
                lines.append(f"{r['snippet'][:200]}")
            lines.append("")

        return "\n".join(lines)
    except Exception as e:
        return f"Error searching wiki: {e}"
