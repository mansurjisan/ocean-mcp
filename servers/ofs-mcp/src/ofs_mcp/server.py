"""FastMCP server entry point for OFS MCP."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import OFSClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared OFS client lifecycle."""
    client = OFSClient()
    try:
        yield {"ofs_client": client}
    finally:
        await client.close()


mcp = FastMCP("ofs_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import discovery, forecast  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
