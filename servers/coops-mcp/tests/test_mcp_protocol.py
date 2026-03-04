"""MCP protocol tests for coops-mcp server."""

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_server_starts_and_lists_tools():
    """Verify the MCP server starts and registers all expected tools."""
    server_params = StdioServerParameters(command="python", args=["-m", "coops_mcp"])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}

            # coops-mcp should register 12 tools
            assert len(tools.tools) >= 11, (
                f"Expected at least 11 tools, got {len(tools.tools)}"
            )

            # Check key tools exist
            expected = {
                "coops_list_stations",
                "coops_get_station",
                "coops_find_nearest_stations",
                "coops_get_water_levels",
                "coops_get_tide_predictions",
                "coops_get_currents",
                "coops_get_meteorological",
                "coops_get_extreme_water_levels",
                "coops_get_flood_stats",
                "coops_get_sea_level_trends",
                "coops_get_peak_storm_events",
                "coops_get_datums",
            }
            missing = expected - tool_names
            assert not missing, f"Missing tools: {missing}"
