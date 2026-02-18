"""FastMCP server entry point for NHC MCP."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import NHCClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared NHC API client lifecycle."""
    client = NHCClient()
    try:
        yield {"nhc_client": client}
    finally:
        await client.close()


mcp = FastMCP("nhc_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import active, forecast, history  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
