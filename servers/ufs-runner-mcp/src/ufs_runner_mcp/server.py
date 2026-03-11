"""FastMCP server entry point for UFS Runner."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .runner import UfsRunner


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared UFS runner lifecycle."""
    runner = UfsRunner()
    try:
        yield {"ufs_runner": runner}
    finally:
        pass  # No cleanup needed for subprocess-based runner


mcp = FastMCP("ufs_runner_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import experiment, monitoring  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
