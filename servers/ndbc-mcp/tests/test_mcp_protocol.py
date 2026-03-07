"""MCP protocol tests for ndbc-mcp server."""

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_server_starts_and_lists_tools():
    """Verify the MCP server starts and registers all expected tools."""
    server_params = StdioServerParameters(command="python", args=["-m", "ndbc_mcp"])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}

            assert len(tools.tools) >= 8, (
                f"Expected at least 8 tools, got {len(tools.tools)}"
            )

            expected = {
                "ndbc_list_stations",
                "ndbc_get_station",
                "ndbc_find_nearest_stations",
                "ndbc_get_latest_observation",
                "ndbc_get_observations",
                "ndbc_get_wave_summary",
                "ndbc_get_daily_summary",
                "ndbc_compare_stations",
            }
            missing = expected - tool_names
            assert not missing, f"Missing tools: {missing}"
