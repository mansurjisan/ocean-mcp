"""MCP protocol tests for recon-mcp server."""

import sys
import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_server_starts_and_lists_tools():
    """Verify the MCP server starts and registers all expected tools."""
    server_params = StdioServerParameters(
        command=sys.executable, args=["-m", "recon_mcp"]
    )
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


@pytest.mark.asyncio
async def test_response_format_is_a_real_enum_in_the_tool_schema():
    """response_format must be a Literal enum in the MCP schema, not a bare str.

    A Literal is only enforced at the MCP boundary (the JSON schema), not on
    direct Python calls — so a unit test calling the tool function directly
    would not catch a bare `str` or a wrong/missing enum. This inspects the
    actual inputSchema returned by list_tools() over the stdio transport.
    """
    server_params = StdioServerParameters(
        command=sys.executable, args=["-m", "recon_mcp"]
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tools_by_name = {t.name: t for t in tools.tools}

            tools_with_response_format = {
                "recon_get_hdobs",
                "recon_get_vdms",
                "recon_get_fixes",
                "recon_list_missions",
                "recon_list_sfmr",
                "recon_get_sfmr",
            }
            for name in tools_with_response_format:
                tool = tools_by_name[name]
                props = tool.inputSchema["properties"]
                assert "response_format" in props, f"{name} is missing response_format"
                schema = props["response_format"]
                # A Literal[...] renders as an "enum" list in the JSON schema
                # (possibly nested under anyOf/allOf depending on defaults);
                # a bare `str` would have no "enum" key at all.
                enum = schema.get("enum")
                if enum is None:
                    for branch in schema.get("anyOf", []) + schema.get("allOf", []):
                        if "enum" in branch:
                            enum = branch["enum"]
                            break
                assert enum is not None, (
                    f"{name}.response_format has no enum in its schema: {schema}"
                )
                assert set(enum) == {"markdown", "json"}, (
                    f"{name}.response_format enum is {enum}, expected exactly "
                    "{'markdown', 'json'}"
                )
