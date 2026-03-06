"""MCP protocol tests for goes-mcp server."""

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_server_starts_and_lists_tools():
    """Verify the GOES MCP server starts and registers all 6 expected tools."""
    server_params = StdioServerParameters(command="python", args=["-m", "goes_mcp"])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}

            # goes-mcp should register exactly 6 tools
            assert len(tools.tools) == 6, (
                f"Expected 6 tools, got {len(tools.tools)}: {tool_names}"
            )

            expected = {
                "goes_list_products",
                "goes_get_available_times",
                "goes_get_latest_image",
                "goes_get_image",
                "goes_get_sector_image",
                "goes_get_current_view",
            }
            missing = expected - tool_names
            assert not missing, f"Missing tools: {missing}"
