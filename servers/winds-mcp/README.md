# winds-mcp

MCP server providing access to NWS surface wind observations from ASOS, AWOS, and other stations.

## Data Sources

| Source | Coverage | Auth |
|--------|----------|------|
| [NWS Weather.gov API](https://api.weather.gov) | All NWS stations, latest/recent observations | None (User-Agent header) |
| [Iowa Environmental Mesonet](https://mesonet.agron.iastate.edu) | Historical ASOS archive (~2000+) | None |

## Tools (8)

### Station Discovery
- **`winds_list_stations`** — List NWS stations by US state
- **`winds_get_station`** — Get detailed station metadata
- **`winds_find_nearest_stations`** — Find stations near a lat/lon

### Observations
- **`winds_get_latest_observation`** — Most recent observation at a station
- **`winds_get_observations`** — Recent observations over a time window (up to 7 days)
- **`winds_get_history`** — Historical ASOS data from IEM archive (back to ~2000)
- **`winds_get_daily_summary`** — Daily wind statistics from IEM archive
- **`winds_compare_stations`** — Compare latest observations across multiple stations

## Installation

```bash
# Using uvx (recommended)
uvx winds-mcp

# Using pip
pip install winds-mcp
```

## Usage with Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "winds": {
      "command": "uvx",
      "args": ["winds-mcp"]
    }
  }
}
```

## Development

```bash
cd servers/winds-mcp
uv sync --group dev
uv run pytest tests/ --ignore=tests/test_live.py --ignore=tests/test_mcp_protocol.py -v
```
