"""FastMCP server entry point for ERDDAP MCP."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import ERDDAPClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared ERDDAP API client lifecycle."""
    client = ERDDAPClient()
    try:
        yield {"erddap_client": client}
    finally:
        await client.close()


mcp = FastMCP("erddap_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import griddap, metadata, search, tabledap  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
