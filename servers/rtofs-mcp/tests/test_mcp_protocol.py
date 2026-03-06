"""MCP protocol lifecycle test for RTOFS MCP server."""

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_mcp_server_starts_and_lists_tools():
    """Verify RTOFS MCP server starts and lists all expected tools."""
    server_params = StdioServerParameters(command="python", args=["-m", "rtofs_mcp"])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools_result = await session.list_tools()
            tool_names = {t.name for t in tools_result.tools}

            # Verify expected tool count
            assert len(tool_names) >= 8, (
                f"Expected at least 8 tools, got {len(tool_names)}: {tool_names}"
            )

            # Verify key tools are present
            expected = [
                "rtofs_get_system_info",
                "rtofs_list_datasets",
                "rtofs_get_latest_time",
                "rtofs_get_surface_forecast",
                "rtofs_get_profile_forecast",
                "rtofs_get_area_forecast",
                "rtofs_get_transect",
                "rtofs_compare_with_observations",
            ]
            for name in expected:
                assert name in tool_names, f"Expected tool '{name}' not found"
