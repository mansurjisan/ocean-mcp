# ndbc-mcp

MCP server providing access to NOAA National Data Buoy Center (NDBC) observations from 1,300+ offshore stations.

## Features

- Real-time buoy observations: wind, waves, SST, pressure, air temperature
- Spectral wave data with swell/wind-wave separation
- Station discovery by location, type, or owner
- Daily statistical summaries (min/max/mean)
- Multi-station comparison

## Data Sources

- **NDBC Realtime2**: `https://www.ndbc.noaa.gov/data/realtime2/` -- 45-day rolling archive, updated every ~10 min
- **Active Stations XML**: `https://www.ndbc.noaa.gov/activestations.xml` -- 1,350 stations with metadata

No API keys required.

## Installation

```bash
# Using uvx (recommended)
uvx ndbc-mcp

# Using pip
pip install ndbc-mcp
```

## Tools

| Tool | Description |
|------|-------------|
| `ndbc_list_stations` | List active stations with filters (type, owner, met sensors) |
| `ndbc_get_station` | Get metadata for a specific station |
| `ndbc_find_nearest_stations` | Find stations near a lat/lon coordinate |
| `ndbc_get_latest_observation` | Latest observation (all variables) |
| `ndbc_get_observations` | Time series from realtime2 (configurable hours) |
| `ndbc_get_wave_summary` | Spectral wave summary (swell/wind-wave separation) |
| `ndbc_get_daily_summary` | Daily min/max/mean for key variables |
| `ndbc_compare_stations` | Side-by-side comparison of 2-10 stations |

## Configuration

### Claude Desktop

```json
{
  "mcpServers": {
    "ndbc": {
      "command": "uvx",
      "args": ["ndbc-mcp"]
    }
  }
}
```

## License

MIT
