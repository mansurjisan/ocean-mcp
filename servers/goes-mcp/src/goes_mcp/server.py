"""FastMCP server entry point for GOES satellite imagery."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import GOESClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared GOES API client lifecycle."""
    client = GOESClient()
    try:
        yield {"goes_client": client}
    finally:
        await client.close()


mcp = FastMCP("goes_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import imagery, products  # noqa: E402, F401


def main() -> None:
    """Run the GOES MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
