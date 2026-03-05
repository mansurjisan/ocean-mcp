"""Documentation fetching tools — access SCHISM docs."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import SchismClient, SchismClientError
from ..models import SCHISM_DOCS_BASE
from ..server import mcp


def _get_client(ctx: Context) -> SchismClient:
    return ctx.request_context.lifespan_context["schism_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def schism_fetch_docs(
    ctx: Context,
    topic: str,
) -> str:
    """Fetch documentation from the SCHISM documentation site.

    Retrieves page content as plain text.

    Args:
        topic: Documentation path or topic (e.g., 'input-output/param.nml.html', 'getting-started/troubleshooting.html').
    """
    try:
        client = _get_client(ctx)

        # If topic doesn't end with .html, try to find the right path
        if not topic.endswith(".html"):
            results = await client.search_docs(topic)
            if results:
                # Use the best match
                path = results[0]["url"].replace(SCHISM_DOCS_BASE + "/", "")
                content = await client.fetch_doc_page(path)
            else:
                return f"No documentation found for '{topic}'. Try `schism_search_docs` to search."
        else:
            content = await client.fetch_doc_page(topic)

        if not content:
            return f"No content found for '{topic}'. Try `schism_search_docs` to find related pages."

        # Truncate if too long
        max_length = 4000
        if len(content) > max_length:
            content = (
                content[:max_length]
                + f"\n\n... (truncated, full page at {SCHISM_DOCS_BASE}/{topic})"
            )

        lines = [f"## SCHISM Documentation: {topic}"]
        lines.append(f"*Source: {SCHISM_DOCS_BASE}/{topic}*\n")
        lines.append(content)

        return "\n".join(lines)
    except SchismClientError as e:
        return f"Documentation error: {e}. Try `schism_search_docs` to find the correct page."
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
async def schism_search_docs(
    ctx: Context,
    query: str,
) -> str:
    """Search SCHISM documentation and return matching pages.

    Args:
        query: Search terms (e.g., 'param.nml', 'vertical grid', 'hotstart').
    """
    try:
        client = _get_client(ctx)
        results = await client.search_docs(query)

        if not results:
            return f"No results found for '{query}'. Try different search terms or check {SCHISM_DOCS_BASE} directly."

        lines = [f"## SCHISM Documentation Search: '{query}'"]
        lines.append(f"*{len(results)} results found*\n")

        for r in results:
            lines.append(f"### [{r['title']}]({r['url']})")
            lines.append(f"{r['description']}")
            lines.append("")

        return "\n".join(lines)
    except Exception as e:
        return f"Error searching documentation: {e}"
