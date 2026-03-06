"""FastMCP server entry point for USGS Water Services."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import USGSClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared USGSClient lifecycle."""
    client = USGSClient()
    try:
        yield {"usgs_client": client}
    finally:
        await client.close()


mcp = FastMCP("usgs_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import flood, sites, statistics, streamflow  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
