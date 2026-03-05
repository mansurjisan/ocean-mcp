# ww3-mcp

MCP server for **NOAA GFS-Wave (WAVEWATCH III)** forecasts and **NDBC buoy** wave observations.

## Features

- **GFS-Wave Forecasts** — Wave height, period, direction from NOMADS GRIB2 data (up to 16 days)
- **NDBC Buoy Observations** — Realtime and historical wave measurements from ~1000+ buoys
- **Model Validation** — Compare GFS-Wave forecasts against buoy observations

## Tools (9)

### Discovery
| Tool | Description |
|------|-------------|
| `ww3_list_grids` | List 6 GFS-Wave grids with resolution and domain info |
| `ww3_list_cycles` | Check available forecast cycles on NOAA servers |
| `ww3_find_buoys` | Find NDBC buoys near a geographic location |

### Buoy Observations
| Tool | Description |
|------|-------------|
| `ww3_get_buoy_observations` | Recent wave observations from an NDBC buoy |
| `ww3_get_buoy_history` | Historical annual wave data from NDBC archive |

### Wave Forecasts
| Tool | Description |
|------|-------------|
| `ww3_get_forecast_at_point` | GFS-Wave forecast time series at a lat/lon |
| `ww3_get_point_snapshot` | All wave variables at a single point/time |
| `ww3_get_regional_summary` | Spatial statistics over a bounding box |
| `ww3_compare_forecast_with_buoy` | Model vs buoy validation (bias, RMSE, MAE) |

## Installation

```bash
# Using uvx (recommended)
uvx ww3-mcp

# Or install with pip
pip install ww3-mcp
```

## Configuration

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ww3": {
      "command": "uvx",
      "args": ["ww3-mcp"]
    }
  }
}
```

## Data Sources

- **NOMADS Grib Filter** — GFS-Wave GRIB2 data subsetted by variable and region
- **AWS S3 (noaa-gfs-bdp-pds)** — Cycle availability checks
- **NDBC Realtime2** — ~45 days of buoy observations
- **NDBC Active Stations** — Station registry XML

All data sources are free, public NOAA APIs. No API keys required.

## Development

```bash
cd servers/ww3-mcp
uv sync --group dev
uv run pytest tests/ --ignore=tests/test_live.py --ignore=tests/test_mcp_protocol.py -v
```

## License

MIT

<!-- mcp-name: io.github.mansurjisan/ww3-mcp -->
