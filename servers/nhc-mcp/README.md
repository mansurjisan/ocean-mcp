# NHC MCP Server

MCP server providing AI assistants with access to National Hurricane Center (NHC) storm tracks, advisories, and best track data.

**Status: Ready**

## Tools

| Tool | Description | Status |
|------|-------------|--------|
| `nhc_get_active_storms` | Get currently active tropical cyclones | Ready |
| `nhc_get_forecast_track` | Get official NHC 5-day forecast track positions | Ready |
| `nhc_get_best_track` | Get best track data for historical or recent storms | Ready |
| `nhc_search_storms` | Search historical storms by name, year, basin, intensity | Ready |
| `nhc_get_storm_watches_warnings` | Get active watches and warnings for a storm | Ready |
| `nhc_generate_parametric_wind` | Generate parametric wind field for a storm | Planned |

## Data Sources

- **CurrentStorms.json** — Real-time active storm information from NHC
- **ATCF B-deck** — Current-season best track data (Automated Tropical Cyclone Forecasting)
- **HURDAT2** — Atlantic (1851–2024) and East Pacific (1949–2024) hurricane database
- **NHC ArcGIS MapServer** — Forecast tracks, cones, and watch/warning polygons

## Quick Start

```bash
git clone https://github.com/mansurjisan/ocean-mcp.git
cd ocean-mcp/servers/nhc-mcp
uv sync
```

### Configure your MCP client

```json
{
  "mcpServers": {
    "nhc": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/nhc-mcp", "python", "-m", "nhc_mcp"]
    }
  }
}
```

## Example Queries

- "Are there any active tropical cyclones right now?"
- "Show me Hurricane Katrina's track"
- "Search for Category 5 hurricanes in the Atlantic since 2000"
- "What is the forecast track for the active storm AL052024?"
- "Find all storms named Maria"

## Running Tests

```bash
# Unit tests (fast, no network)
uv run pytest tests/test_utils.py tests/test_client.py -v

# Live integration tests (requires internet)
uv run pytest tests/test_live.py -v -s
```

## License

MIT
