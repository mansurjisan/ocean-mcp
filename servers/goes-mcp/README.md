# goes-mcp

MCP server for **NOAA GOES satellite imagery** — visible, infrared, water vapor, and composite products from GOES-18 (West) and GOES-19 (East).

## Features

- **16 ABI spectral bands** — visible, near-IR, and infrared channels
- **6 composite products** — GeoColor, AirMass, Sandwich, Fire Temperature, Dust, Derived Motion Winds
- **Multiple coverages** — CONUS, Full Disk, and 5 regional sectors (SE, NE, Caribbean, Tropical Atlantic, Puerto Rico)
- **Image embedding** — returns JPEG images directly via MCP `Image` type
- **Flexible output** — image (default), markdown with URL, or JSON metadata

## Data Sources

- **NOAA STAR CDN** (`cdn.star.nesdis.noaa.gov`) — pre-rendered JPEG imagery at multiple resolutions
- **RAMMB/CIRA SLIDER** (`slider.cira.colostate.edu`) — timestamp discovery for historical imagery

No API keys required. All data is freely available from NOAA.

## Tools

| Tool | Description |
|------|-------------|
| `goes_list_products` | List all available bands, composites, coverages, and sectors |
| `goes_get_available_times` | Get recent image timestamps for a product (via SLIDER API) |
| `goes_get_latest_image` | Fetch the most recent satellite image |
| `goes_get_image` | Fetch a satellite image for a specific timestamp |
| `goes_get_sector_image` | Fetch latest imagery for a regional sector |
| `goes_get_current_view` | Overview of current imagery availability |

## Installation

```bash
# With uv (recommended)
uvx goes-mcp

# With pip
pip install goes-mcp
```

## Usage with Claude Desktop

Add to your Claude Desktop config:

```json
{
  "mcpServers": {
    "goes": {
      "command": "uvx",
      "args": ["goes-mcp"]
    }
  }
}
```

## Example Queries

- "Show me the latest GOES-East GeoColor image of the Continental US"
- "Get a satellite view of the Caribbean right now"
- "What satellite imagery is currently available?"
- "Show me infrared band 13 for the full disk view"
- "Get the latest fire temperature composite for the Southeast US"

## Development

```bash
cd servers/goes-mcp
uv sync --group dev

# Run unit tests
uv run pytest tests/ --ignore=tests/test_live.py --ignore=tests/test_mcp_protocol.py -v

# Run MCP protocol test
uv run pytest tests/test_mcp_protocol.py -v

# Run live integration tests (requires network)
uv run pytest tests/test_live.py -v

# Lint
uv run ruff check src/ tests/ --select E,F,W --ignore E501
uv run ruff format --check src/ tests/
```

## License

MIT
