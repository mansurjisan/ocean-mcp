# Ocean MCP — Real-Time Marine Data, MCP-Native

A monorepo of independently installable MCP servers for ocean and coastal data workflows.

## Servers

| Server | Description | Status |
|--------|-------------|--------|
| [coops-mcp](servers/coops-mcp/) | NOAA CO-OPS tides, water levels, currents, meteorological data | Ready |
| [erddap-mcp](servers/erddap-mcp/) | Universal ERDDAP data access across 80+ public servers | Ready |
| [nhc-mcp](servers/nhc-mcp/) | NHC storm tracks, advisories, HURDAT2 best track data | Ready |
| [stofs-mcp](servers/stofs-mcp/) | NOAA STOFS storm surge forecasts and observation validation | Ready |

## Quick Start

### Install a single server

```bash
git clone https://github.com/mansurjisan/ocean-mcp.git
cd ocean-mcp/servers/coops-mcp  # or erddap-mcp, nhc-mcp, stofs-mcp
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
    },
    "nhc": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/nhc-mcp", "python", "-m", "nhc_mcp"]
    },
    "stofs": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/stofs-mcp", "python", "-m", "stofs_mcp"]
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

**NHC queries:**
- "Are there any active tropical cyclones right now?"
- "Show me Hurricane Katrina's track"
- "Search for Category 5 hurricanes in the Atlantic"
- "What is the forecast track for the active storm?"

**STOFS queries:**
- "Get the STOFS water level forecast for The Battery, NY"
- "Compare STOFS forecast vs observations at Boston for the past 24 hours"
- "What are the top stations with highest predicted water levels?"
- "Find STOFS stations within 50 km of New Orleans"

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

## Citation

If you use this project in your research or work, please cite:

```bibtex
@software{jisan2025oceanmcp,
  author    = {Jisan, Mansur Ali},
  title     = {Ocean MCP: Real-Time Marine Data, MCP-Native},
  year      = {2025},
  url       = {https://github.com/mansurjisan/ocean-mcp},
  note      = {MCP servers for NOAA CO-OPS, ERDDAP, NHC, and STOFS data}
}
```

## License

Licensed under the MIT License. See [LICENSE](LICENSE) for details.
