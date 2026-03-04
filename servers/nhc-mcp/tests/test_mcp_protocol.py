"""MCP protocol tests for nhc-mcp server."""

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_server_starts_and_lists_tools():
    """Verify the MCP server starts and registers all expected tools."""
    server_params = StdioServerParameters(
        command="python", args=["-m", "nhc_mcp"]
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}

            assert len(tools.tools) >= 5, f"Expected at least 5 tools, got {len(tools.tools)}"

            expected = {
                "nhc_get_active_storms",
                "nhc_get_forecast_track",
                "nhc_get_storm_watches_warnings",
                "nhc_get_best_track",
                "nhc_search_storms",
            }
            missing = expected - tool_names
            assert not missing, f"Missing tools: {missing}"
