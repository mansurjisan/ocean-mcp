"""FastMCP server entry point for SCHISM MCP."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .client import SchismClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared SCHISM client lifecycle."""
    client = SchismClient()
    try:
        yield {"schism_client": client}
    finally:
        await client.close()


mcp = FastMCP("schism_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import docs, parsing, reference, validation  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
