"""MCP protocol tests for schism-mcp server."""

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_server_starts_and_lists_tools():
    """Verify the MCP server starts and registers all 10 expected tools."""
    server_params = StdioServerParameters(command="python", args=["-m", "schism_mcp"])
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}

            assert len(tools.tools) >= 10, (
                f"Expected at least 10 tools, got {len(tools.tools)}"
            )

            expected = {
                "schism_explain_parameter",
                "schism_list_parameters",
                "schism_parse_param_nml",
                "schism_parse_hgrid",
                "schism_parse_vgrid",
                "schism_parse_bctides",
                "schism_validate_config",
                "schism_diagnose_error",
                "schism_fetch_docs",
                "schism_search_docs",
            }
            missing = expected - tool_names
            assert not missing, f"Missing tools: {missing}"
