"""FastMCP server for NOS OFS workflow management."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .config_reader import ConfigReader


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared config reader lifecycle."""
    reader = ConfigReader()
    try:
        yield {"config_reader": reader}
    finally:
        pass


mcp = FastMCP("nos_workflow_mcp", lifespan=app_lifespan)

from .tools import config, diagnostics, validation, availability, tracker  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
