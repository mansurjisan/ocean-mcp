# CO-OPS MCP Server

MCP server providing AI assistants with access to NOAA CO-OPS water levels, tides, currents, and coastal oceanographic data.

**No API key required** — all CO-OPS APIs are free and public.

## Features

- **Station Discovery** — List, search, and find nearest CO-OPS stations by type, state, or coordinates
- **Water Levels** — Real-time and historical observed water levels with multiple datum references
- **Tide Predictions** — Harmonic tide predictions (6-min, hourly, or high/low)
- **Meteorological Data** — Wind, air/water temperature, pressure, humidity, visibility, and more
- **Currents** — Current observations and predictions from PORTS stations
- **Derived Products** — Extreme water levels, flood statistics, sea level trends, storm events, tidal datums

## Quick Start

### Install with uv

```bash
git clone https://github.com/mansurjisan/ocean-mcp.git
cd ocean-mcp/servers/coops-mcp
uv sync
```

### Configure your MCP client

Add to your MCP settings:

```json
{
  "mcpServers": {
    "coops": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/coops-mcp", "python", "-m", "coops_mcp"]
    }
  }
}
```

Or if installed as a package:

```json
{
  "mcpServers": {
    "coops": {
      "command": "uvx",
      "args": ["coops-mcp"]
    }
  }
}
```

## Available Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `coops_list_stations` | List CO-OPS stations by type/state | `station_type`, `state`, `limit` |
| `coops_get_station` | Get detailed station metadata | `station_id`, `expand` (sensors, datums, etc.) |
| `coops_find_nearest_stations` | Find stations near coordinates | `latitude`, `longitude`, `radius_km` |
| `coops_get_water_levels` | Observed water level data | `station_id`, `begin_date`, `end_date`, `datum` |
| `coops_get_tide_predictions` | Tide predictions | `station_id`, `begin_date`, `end_date`, `interval` |
| `coops_get_meteorological` | Met observations (wind, temp, etc.) | `station_id`, `product`, `date` |
| `coops_get_currents` | Current observations/predictions | `station_id`, `product`, `bin_num` |
| `coops_get_extreme_water_levels` | Record water levels | `station_id`, `datum` |
| `coops_get_flood_stats` | Flood day counts & HTF outlook | `station_id`, `year` |
| `coops_get_sea_level_trends` | Sea level trend data | `station_id` |
| `coops_get_peak_storm_events` | Peak storm surge events | `station_id`, `year` |
| `coops_get_datums` | Tidal datum values | `station_id`, `units` |

## Usage Examples

Ask naturally — the right tool will be selected automatically:

- **"Get current water levels at The Battery, NY"** → `coops_get_water_levels(station_id="8518750", date="latest")`
- **"Find tide stations near Miami Beach"** → `coops_find_nearest_stations(latitude=25.77, longitude=-80.13, station_type="waterlevels")`
- **"What were the highest water levels ever recorded at San Francisco?"** → `coops_get_extreme_water_levels(station_id="9414290")`
- **"Show me wind data for Key West today"** → `coops_get_meteorological(station_id="8724580", product="wind", date="today")`
- **"What are the flood statistics for The Battery?"** → `coops_get_flood_stats(station_id="8518750")`
- **"Get tide predictions for Charleston, SC for next week"** → `coops_get_tide_predictions(station_id="8665530", begin_date="...", end_date="...")`

## API Reference

This server wraps three NOAA CO-OPS APIs:

- [Data API](https://tidesandcurrents.noaa.gov/api/) — Observations and predictions
- [Metadata API](https://tidesandcurrents.noaa.gov/mdapi/latest/) — Station information
- [Derived Product API](https://api.tidesandcurrents.noaa.gov/dpapi/prod/) — Historical/statistical products

## Development

```bash
# Install dev dependencies
uv sync

# Run unit tests
uv run pytest tests/test_models.py tests/test_utils.py tests/test_client.py -v

# Run live integration tests (makes real API calls)
uv run pytest tests/test_live.py -v -s

# Start the server
uv run python -m coops_mcp
```

## License

MIT
