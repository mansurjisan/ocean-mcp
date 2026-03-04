"""MCP protocol tests for stofs-mcp server."""

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_server_starts_and_lists_tools():
    """Verify the MCP server starts and registers all expected tools."""
    server_params = StdioServerParameters(command="python", args=["-m", "stofs_mcp"])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}

            assert len(tools.tools) >= 8, (
                f"Expected at least 8 tools, got {len(tools.tools)}"
            )

            expected = {
                "stofs_list_cycles",
                "stofs_get_system_info",
                "stofs_list_stations",
                "stofs_get_station_forecast",
                "stofs_get_point_forecast",
                "stofs_get_max_water_level",
                "stofs_get_gridded_forecast",
                "stofs_compare_with_observations",
            }
            missing = expected - tool_names
            assert not missing, f"Missing tools: {missing}"
