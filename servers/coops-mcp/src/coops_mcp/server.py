"""FastMCP server entry point for CO-OPS MCP."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import COOPSClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared CO-OPS API client lifecycle."""
    client = COOPSClient()
    try:
        yield {"coops_client": client}
    finally:
        await client.close()


mcp = FastMCP("coops_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import currents, derived, meteorological, stations, water_levels  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
