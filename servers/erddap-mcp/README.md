# ERDDAP MCP Server

<!-- mcp-name: io.github.mansurjisan/erddap-mcp -->

MCP server providing AI assistants with access to ocean data from ERDDAP servers worldwide. ERDDAP is the backbone of ocean data distribution — NOAA CoastWatch, IOOS regional associations, and 80+ institutions run ERDDAP servers.

**No API key required** — all ERDDAP data is free and public.

## Features

- **Server Registry** — 11 well-known ERDDAP servers with region and topic filtering
- **Dataset Search** — Free-text search across any ERDDAP server
- **Dataset Metadata** — Variables, dimensions, time/spatial coverage, attributes
- **Tabledap Data** — In-situ/tabular data (buoys, gliders, ship tracks) with constraint filtering
- **Griddap Data** — Gridded/satellite data (SST, chlorophyll, currents) with dimension subsetting
- **Dataset Listing** — Browse all datasets on any server with filtering

## Quick Start

### Install with uv

```bash
git clone https://github.com/mansurjisan/ocean-mcp.git
cd ocean-mcp/servers/erddap-mcp
uv sync
```

### Configure your MCP client

```json
{
  "mcpServers": {
    "erddap": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/erddap-mcp", "python", "-m", "erddap_mcp"]
    }
  }
}
```

## Available Tools

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `erddap_list_servers` | List known ERDDAP servers | `region`, `keyword` |
| `erddap_search_datasets` | Search for datasets | `search_for`, `server_url`, `protocol` |
| `erddap_get_dataset_info` | Get dataset metadata | `server_url`, `dataset_id` |
| `erddap_get_tabledap_data` | Get tabular data | `server_url`, `dataset_id`, `variables`, `constraints` |
| `erddap_get_griddap_data` | Get gridded data | `server_url`, `dataset_id`, `time_range`, `latitude_range`, `longitude_range` |
| `erddap_get_all_datasets` | List all server datasets | `server_url`, `protocol`, `institution` |

## Known ERDDAP Servers

| Name | Focus | Region |
|------|-------|--------|
| CoastWatch West Coast | Satellite, SST, chlorophyll | US West Coast |
| CoastWatch CWHDF | Gulf of Mexico | Gulf of Mexico |
| IOOS Gliders | Underwater glider data | US National |
| NCEI | Climate/archive data | Global |
| OSMC | Observing system monitoring | Global |
| NERACOOS | NE US regional ocean obs | US East Coast |
| PacIOOS | Pacific Islands | Pacific |
| BCO-DMO | Bio/chemical ocean data | Global |
| NOAA UAF | Fisheries, upwelling | US West Coast |
| OOI | Ocean Observatories Initiative | US National |
| SECOORA | SE US regional ocean obs | US East Coast |

## Usage Examples

- **"Search for sea surface temperature datasets"** → `erddap_search_datasets(search_for="sea surface temperature")`
- **"What variables are in the MUR SST dataset?"** → `erddap_get_dataset_info(dataset_id="jplMURSST41")`
- **"Get recent chlorophyll data off the California coast"** → `erddap_get_griddap_data(dataset_id="erdMH1chlamday", latitude_range=[32, 42], longitude_range=[-125, -117])`
- **"Find NDBC buoy data near San Francisco"** → `erddap_get_tabledap_data(dataset_id="cwwcNDBCMet", constraints={"latitude>=": 37, "latitude<=": 38})`
- **"What ERDDAP servers cover the US East Coast?"** → `erddap_list_servers(region="East Coast")`

## Development

```bash
# Install dev dependencies
uv sync

# Run live integration tests (makes real API calls)
uv run pytest tests/test_live.py -v -s

# Start the server
uv run python -m erddap_mcp
```

## License

MIT
