"""MCP protocol tests for winds-mcp server."""

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_server_starts_and_lists_tools():
    """Verify the MCP server starts and registers all expected tools."""
    server_params = StdioServerParameters(command="python", args=["-m", "winds_mcp"])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}

            # winds-mcp should register 8 tools
            assert len(tools.tools) >= 8, (
                f"Expected at least 8 tools, got {len(tools.tools)}"
            )

            expected = {
                "winds_list_stations",
                "winds_get_station",
                "winds_find_nearest_stations",
                "winds_get_latest_observation",
                "winds_get_observations",
                "winds_get_history",
                "winds_get_daily_summary",
                "winds_compare_stations",
            }
            missing = expected - tool_names
            assert not missing, f"Missing tools: {missing}"
