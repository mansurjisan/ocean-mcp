"""FastMCP server for NOAA RDHPCS HPC system management."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from .executor import CommandExecutor


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Manage the shared command executor lifecycle."""
    executor = CommandExecutor()
    try:
        yield {"executor": executor}
    finally:
        pass


mcp = FastMCP("hpc_system_mcp", lifespan=app_lifespan)

# Import tool modules to register them with the server
from .tools import quota, allocation, modules, system, pbs  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
