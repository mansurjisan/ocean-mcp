# Ocean MCP — AI Tools for Ocean Science

A monorepo of MCP (Model Context Protocol) servers that give AI assistants access to ocean science data. Each server is independently installable and focuses on a specific data source.

## Servers

| Server | Description | Status |
|--------|-------------|--------|
| [coops-mcp](servers/coops-mcp/) | NOAA CO-OPS tides, water levels, currents, meteorological data | Ready |
| [erddap-mcp](servers/erddap-mcp/) | Universal ERDDAP data access across 80+ public servers | Ready |
| [nhc-mcp](servers/nhc-mcp/) | NHC storm tracks, advisories, HURDAT2 best track data | Planned |
| schism-mcp | SCHISM model config/namelist tools | Planned |
| stofs-mcp | STOFS operational forecast products | Planned |

## Quick Start

### Install a single server

```bash
git clone https://github.com/MansurAI-Jisan/ocean-mcp.git
cd ocean-mcp/servers/coops-mcp  # or erddap-mcp
uv sync
```

### Configure your MCP client for multiple servers

Add to your MCP settings (e.g., project `.mcp.json`):

```json
{
  "mcpServers": {
    "coops": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/coops-mcp", "python", "-m", "coops_mcp"]
    },
    "erddap": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/erddap-mcp", "python", "-m", "erddap_mcp"]
    }
  }
}
```

## Example Queries

With both servers configured, you can ask your AI assistant naturally:

**CO-OPS queries:**
- "Get current water levels at The Battery, NY"
- "Find tide stations near Miami Beach"
- "What are the flood statistics for Charleston, SC?"
- "Show me the sea level trend at San Francisco"

**ERDDAP queries:**
- "Search for sea surface temperature datasets on CoastWatch"
- "Get chlorophyll data off the California coast for January 2024"
- "What ERDDAP servers cover the US East Coast?"
- "List all glider datasets on IOOS Gliders ERDDAP"

**Cross-server queries:**
- "Find CO-OPS stations near this ERDDAP buoy location"
- "Compare tide station data with nearby ERDDAP satellite SST"

## Architecture

Each server is fully self-contained with its own `pyproject.toml`, dependencies, and tests. See [docs/architecture.md](docs/architecture.md) for details on shared conventions.

**Shared patterns across servers:**
- FastMCP for MCP server framework
- httpx for async HTTP clients
- Pydantic for parameter validation
- Read-only tools (no data modification)
- Dual markdown/JSON output formats
- Actionable error messages with suggestions

## Development

```bash
# Work on a specific server
cd servers/coops-mcp
uv sync
uv run pytest tests/ -v

# Run live integration tests
uv run pytest tests/test_live.py -v -s
```

## Contributing

1. Each server is independent — changes to one server should not affect others
2. Follow existing patterns (FastMCP + httpx + Pydantic)
3. All tools must be read-only
4. Include both unit tests and live integration tests
5. Provide actionable error messages

## Author

**Mansur Ali Jisan** — NOAA NOS CO-OPS

## License

MIT — see [LICENSE](LICENSE)
