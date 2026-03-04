"""MCP protocol tests for recon-mcp server."""

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_server_starts_and_lists_tools():
    """Verify the MCP server starts and registers all expected tools."""
    server_params = StdioServerParameters(command="python", args=["-m", "recon_mcp"])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}

            assert len(tools.tools) >= 6, (
                f"Expected at least 6 tools, got {len(tools.tools)}"
            )

            expected = {
                "recon_get_hdobs",
                "recon_get_vdms",
                "recon_get_fixes",
                "recon_list_missions",
                "recon_list_sfmr",
                "recon_get_sfmr",
            }
            missing = expected - tool_names
            assert not missing, f"Missing tools: {missing}"
