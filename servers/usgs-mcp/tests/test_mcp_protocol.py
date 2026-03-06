"""MCP protocol tests for usgs-mcp server lifecycle."""

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "usgs_find_sites",
    "usgs_get_site_info",
    "usgs_find_nearest_sites",
    "usgs_get_instantaneous_values",
    "usgs_get_daily_values",
    "usgs_get_hydrograph",
    "usgs_get_peak_streamflow",
    "usgs_get_flood_status",
    "usgs_get_monthly_stats",
    "usgs_get_daily_stats",
}


@pytest.mark.asyncio
async def test_server_starts_and_lists_tools():
    """Verify usgs-mcp server starts and registers all 10 tools."""
    server_params = StdioServerParameters(command="python", args=["-m", "usgs_mcp"])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}
            assert len(tools.tools) >= 10
            for expected in EXPECTED_TOOLS:
                assert expected in tool_names, f"Missing tool: {expected}"
