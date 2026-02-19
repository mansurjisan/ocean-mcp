"""FastMCP server entry point for STOFS MCP."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import STOFSClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared STOFS client lifecycle."""
    client = STOFSClient()
    try:
        yield {"stofs_client": client}
    finally:
        await client.close()


mcp = FastMCP("stofs_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import discovery, forecast, validation  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
