"""MCP protocol tests for alert-mcp server."""

import sys

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@pytest.mark.asyncio
async def test_server_starts_and_lists_tools():
    """Verify the MCP server starts over stdio and registers all expected tools."""
    server_params = StdioServerParameters(
        command=sys.executable, args=["-m", "alert_mcp"]
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = {t.name for t in tools.tools}

            # alert-mcp should register 7 tools
            assert len(tools.tools) >= 7, (
                f"Expected at least 7 tools, got {len(tools.tools)}"
            )

            expected = {
                "coral_check_alerts",
                "coral_create_alert",
                "coral_delete_alert",
                "coral_get_alert_history",
                "coral_list_alerts",
                "coral_pause_alert",
                "coral_resume_alert",
            }
            missing = expected - tool_names
            assert not missing, f"Missing tools: {missing}"
