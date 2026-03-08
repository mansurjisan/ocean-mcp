"""FastMCP server for NOAA NDBC buoy observations."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import NDBCClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared NDBC client lifecycle."""
    client = NDBCClient()
    try:
        yield {"ndbc_client": client}
    finally:
        await client.close()


mcp = FastMCP("ndbc_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import analysis, observations, stations  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
