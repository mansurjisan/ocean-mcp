"""MCP protocol tests for WW3 MCP server.

Verifies that the server starts correctly, registers all expected tools,
and responds to the MCP protocol lifecycle.
"""

from __future__ import annotations

import pytest

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.integration
class TestMCPProtocol:
    """MCP server lifecycle and tool registration tests."""

    async def test_server_starts_and_lists_tools(self):
        """WW3 MCP server should start and register exactly 9 tools."""
        server_params = StdioServerParameters(command="python", args=["-m", "ww3_mcp"])
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()

                tool_names = {t.name for t in tools.tools}
                assert len(tool_names) == 9, (
                    f"Expected 9 tools, got {len(tool_names)}: {tool_names}"
                )

                expected_tools = {
                    "ww3_list_grids",
                    "ww3_list_cycles",
                    "ww3_find_buoys",
                    "ww3_get_buoy_observations",
                    "ww3_get_buoy_history",
                    "ww3_get_forecast_at_point",
                    "ww3_get_point_snapshot",
                    "ww3_get_regional_summary",
                    "ww3_compare_forecast_with_buoy",
                }
                missing = expected_tools - tool_names
                assert not missing, f"Missing tools: {missing}"
