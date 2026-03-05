"""FastMCP server for NWS surface wind observations."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import WindsClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared WindsClient lifecycle."""
    client = WindsClient()
    try:
        yield {"winds_client": client}
    finally:
        await client.close()


mcp = FastMCP("winds_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import observations, stations  # noqa: E402, F401


def main() -> None:
    mcp.run()
