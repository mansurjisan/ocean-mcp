# usgs-mcp

<!-- mcp-name: io.github.mansurjisan/usgs-mcp -->

MCP server providing access to **USGS Water Services** for real-time streamflow, flood stages, peak events, and historical statistics.

This server fills a critical gap in the ocean-mcp ecosystem by providing **inland flooding and river data** — often the deadliest aspect of hurricanes and storms.

## Data Sources

- **USGS Water Services** (`waterservices.usgs.gov`) — real-time and historical streamflow data
- **USGS NWIS Peak** (`nwis.waterdata.usgs.gov`) — annual peak streamflow records

No API key required. All data is public domain.

## Tools (10)

### Site Discovery
| Tool | Description |
|------|-------------|
| `usgs_find_sites` | Find gauge stations by state or bounding box |
| `usgs_get_site_info` | Get detailed metadata for a specific site |
| `usgs_find_nearest_sites` | Find sites near a lat/lon point |

### Streamflow Data
| Tool | Description |
|------|-------------|
| `usgs_get_instantaneous_values` | Real-time ~15-minute interval data (up to 120 days) |
| `usgs_get_daily_values` | Daily mean/min/max values (decades of history) |
| `usgs_get_hydrograph` | Summary with trend and historical median comparison |

### Flood Analysis
| Tool | Description |
|------|-------------|
| `usgs_get_peak_streamflow` | Annual peak flow records (50+ years at many sites) |
| `usgs_get_flood_status` | Current conditions vs. historical context |

### Statistics
| Tool | Description |
|------|-------------|
| `usgs_get_monthly_stats` | Monthly mean/min/max/percentiles |
| `usgs_get_daily_stats` | Daily percentiles (flow duration) |

## Quick Start

### Install from PyPI
```bash
uvx usgs-mcp
```

### Install from source
```bash
cd servers/usgs-mcp
uv sync
uv run usgs-mcp
```

### Claude Desktop Configuration
```json
{
  "mcpServers": {
    "usgs": {
      "command": "uvx",
      "args": ["usgs-mcp"]
    }
  }
}
```

## Example Queries

- "What is the current streamflow on the Potomac River?" → `usgs_get_instantaneous_values(site_number="01646500")`
- "Find USGS gauges in Texas" → `usgs_find_sites(state_code="TX")`
- "Is the Mississippi at St. Louis flooding?" → `usgs_get_flood_status(site_number="07010000")`
- "What were the biggest floods on the Potomac?" → `usgs_get_peak_streamflow(site_number="01646500")`

## Development

```bash
cd servers/usgs-mcp
uv sync --group dev

# Unit tests (no network)
uv run pytest tests/ --ignore=tests/test_live.py --ignore=tests/test_mcp_protocol.py -v

# Integration tests (needs network)
uv run pytest tests/test_live.py -v

# MCP protocol test
uv run pytest tests/test_mcp_protocol.py -v
```

## License

MIT
