"""FastMCP server for vertical datum conversions."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("vdatum_mcp")

from .tools import convert  # noqa: E402, F401


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
