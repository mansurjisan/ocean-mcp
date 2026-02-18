# NHC MCP Server

MCP server providing AI assistants with access to National Hurricane Center (NHC) storm tracks, advisories, and best track data.

**Status: Coming Soon**

## Planned Tools

| Tool | Description | Status |
|------|-------------|--------|
| `nhc_get_active_storms` | Get currently active tropical cyclones | Coming Soon |
| `nhc_get_forecast_track` | Get official NHC forecast track and cone | Coming Soon |
| `nhc_get_best_track` | Get HURDAT2 best track data for historical storms | Coming Soon |
| `nhc_search_storms` | Search historical storms by name, year, basin | Coming Soon |
| `nhc_get_storm_surge_watch` | Get storm surge watch/warning areas | Coming Soon |
| `nhc_generate_parametric_wind` | Generate parametric wind field for a storm | Coming Soon |

## Data Sources

- **NHC ATCF Feeds** — Automated Tropical Cyclone Forecasting system real-time data
- **HURDAT2** — Atlantic and East Pacific hurricane database (best track archive)
- **IBTrACS** — International Best Track Archive for Climate Stewardship
- **NHC RSS Feeds** — Public advisories, forecast discussions, wind speed probabilities

## Quick Start

```bash
git clone https://github.com/MansurAI-Jisan/ocean-mcp.git
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

## License

MIT
