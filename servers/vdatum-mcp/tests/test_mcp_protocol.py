"""MCP protocol tests for vdatum-mcp server."""

import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_server_starts_and_lists_tools():
    """Verify the MCP server starts over stdio and registers all expected tools."""
    server_params = StdioServerParameters(
        command=sys.executable, args=["-m", "vdatum_mcp"]
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}

            # vdatum-mcp should register 2 tools
            assert len(tools.tools) >= 2, (
                f"Expected at least 2 tools, got {len(tools.tools)}"
            )

            expected = {"vdatum_convert", "vdatum_list_datums"}
            missing = expected - tool_names
            assert not missing, f"Missing tools: {missing}"
