"""MCP protocol tests for adcirc-mcp server."""

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_server_starts_and_lists_tools():
    """Verify the MCP server starts and registers all 10 expected tools."""
    server_params = StdioServerParameters(command="python", args=["-m", "adcirc_mcp"])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}

            assert len(tools.tools) >= 10, (
                f"Expected at least 10 tools, got {len(tools.tools)}"
            )

            expected = {
                "adcirc_explain_parameter",
                "adcirc_list_parameters",
                "adcirc_parse_fort15",
                "adcirc_parse_fort14",
                "adcirc_parse_fort13",
                "adcirc_parse_fort22",
                "adcirc_validate_config",
                "adcirc_diagnose_error",
                "adcirc_fetch_docs",
                "adcirc_search_docs",
            }
            missing = expected - tool_names
            assert not missing, f"Missing tools: {missing}"
