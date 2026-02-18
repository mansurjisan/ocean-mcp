"""FastMCP server entry point for NHC MCP."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("nhc_mcp")


def main():
    mcp.run()


if __name__ == "__main__":
    main()
