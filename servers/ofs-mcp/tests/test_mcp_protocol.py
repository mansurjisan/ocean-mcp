"""MCP protocol tests for ofs-mcp server."""

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_server_starts_and_lists_tools():
    """Verify the MCP server starts and registers all expected tools."""
    server_params = StdioServerParameters(
        command="python", args=["-m", "ofs_mcp"]
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}

            assert len(tools.tools) >= 6, f"Expected at least 6 tools, got {len(tools.tools)}"

            expected = {
                "ofs_list_models",
                "ofs_get_model_info",
                "ofs_list_cycles",
                "ofs_find_models_for_location",
                "ofs_get_forecast_at_point",
                "ofs_compare_with_coops",
            }
            missing = expected - tool_names
            assert not missing, f"Missing tools: {missing}"
