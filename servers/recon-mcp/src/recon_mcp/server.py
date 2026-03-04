"""FastMCP server entry point for Recon MCP."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import ReconClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared Recon API client lifecycle."""
    client = ReconClient()
    try:
        yield {"recon_client": client}
    finally:
        await client.close()


mcp = FastMCP("recon_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import fixes, hdob, missions, sfmr, vdm  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
