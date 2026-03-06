"""FastMCP server entry point for RTOFS MCP."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import RTOFSClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared RTOFS client lifecycle."""
    client = RTOFSClient()
    try:
        yield {"rtofs_client": client}
    finally:
        await client.close()


mcp = FastMCP("rtofs_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import analysis, discovery, forecast  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
