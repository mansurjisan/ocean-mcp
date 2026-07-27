"""FastMCP server for CORAL threshold alerting."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .alert_manager import AlertManager


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared AlertManager (and its underlying HTTP client) lifecycle."""
    manager = AlertManager()
    try:
        yield {"alert_manager": manager}
    finally:
        await manager.close()


mcp = FastMCP("alert_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import alerts  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
