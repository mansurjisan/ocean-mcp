"""FastMCP server entry point for WW3 MCP."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import WW3Client


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared WW3 client lifecycle."""
    client = WW3Client()
    try:
        yield {"ww3_client": client}
    finally:
        await client.close()


mcp = FastMCP("ww3_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import buoy, discovery, forecast  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
