# OceanMCP

A monorepo of independently installable MCP servers for ocean and coastal data workflows.

[![PyPI](https://img.shields.io/pypi/v/coops-mcp)](https://pypi.org/project/coops-mcp/)
[![MCP Registry](https://img.shields.io/badge/MCP_Registry-8_servers-blue)](https://registry.modelcontextprotocol.io/?q=mansurjisan)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Servers

| Server | PyPI | Description |
|--------|------|-------------|
| [coops-mcp](servers/coops-mcp/) | [![PyPI](https://img.shields.io/pypi/v/coops-mcp)](https://pypi.org/project/coops-mcp/) | NOAA CO-OPS tides, water levels, currents, meteorological data |
| [erddap-mcp](servers/erddap-mcp/) | [![PyPI](https://img.shields.io/pypi/v/erddap-mcp)](https://pypi.org/project/erddap-mcp/) | Universal ERDDAP data access across 80+ public servers |
| [nhc-mcp](servers/nhc-mcp/) | [![PyPI](https://img.shields.io/pypi/v/nhc-mcp)](https://pypi.org/project/nhc-mcp/) | NHC storm tracks, advisories, HURDAT2 best track data |
| [recon-mcp](servers/recon-mcp/) | [![PyPI](https://img.shields.io/pypi/v/recon-mcp)](https://pypi.org/project/recon-mcp/) | Hurricane reconnaissance data (HDOB, Vortex Data Messages, ATCF fixes) |
| [stofs-mcp](servers/stofs-mcp/) | [![PyPI](https://img.shields.io/pypi/v/stofs-mcp)](https://pypi.org/project/stofs-mcp/) | NOAA STOFS storm surge forecasts and observation validation |
| [ofs-mcp](servers/ofs-mcp/) | [![PyPI](https://img.shields.io/pypi/v/ofs-mcp)](https://pypi.org/project/ofs-mcp/) | NOAA OFS regional ocean model forecasts (water level, temperature, salinity) |
| [rtofs-mcp](servers/rtofs-mcp/) | [![PyPI](https://img.shields.io/pypi/v/rtofs-mcp)](https://pypi.org/project/rtofs-mcp/) | NOAA RTOFS global ocean forecasts (SST, salinity, currents, SSH) via HYCOM THREDDS |
| [ww3-mcp](servers/ww3-mcp/) | [![PyPI](https://img.shields.io/pypi/v/ww3-mcp)](https://pypi.org/project/ww3-mcp/) | GFS-Wave (WAVEWATCH III) forecasts and NDBC buoy wave observations |

**No API keys required** — all servers use free, publicly available datasets.

## Quick Start

### Install from PyPI

```bash
# uvx (recommended) — runs without permanent install, like npx for Python
uvx coops-mcp

# pip — install into current environment
pip install coops-mcp

# pipx — install in isolated environment with CLI entry point
pipx install coops-mcp
```

Replace `coops-mcp` with any server: `erddap-mcp`, `nhc-mcp`, `recon-mcp`, `stofs-mcp`, `ofs-mcp`, `rtofs-mcp`, `ww3-mcp`.

### Install from source

```bash
git clone https://github.com/mansurjisan/ocean-mcp.git
cd ocean-mcp/servers/coops-mcp  # or erddap-mcp, nhc-mcp, recon-mcp, stofs-mcp, ofs-mcp, rtofs-mcp, ww3-mcp
uv sync
```

### Configure your MCP client

Add to your MCP settings (e.g., project `.mcp.json`):

**Using PyPI packages (recommended):**

```json
{
  "mcpServers": {
    "coops": {
      "command": "uvx",
      "args": ["coops-mcp"]
    },
    "erddap": {
      "command": "uvx",
      "args": ["erddap-mcp"]
    },
    "nhc": {
      "command": "uvx",
      "args": ["nhc-mcp"]
    },
    "recon": {
      "command": "uvx",
      "args": ["recon-mcp"]
    },
    "stofs": {
      "command": "uvx",
      "args": ["stofs-mcp"]
    },
    "ofs": {
      "command": "uvx",
      "args": ["ofs-mcp"]
    },
    "rtofs": {
      "command": "uvx",
      "args": ["rtofs-mcp"]
    },
    "ww3": {
      "command": "uvx",
      "args": ["ww3-mcp"]
    }
  }
}
```

<details>
<summary>Using local source checkout</summary>

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
    "recon": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/recon-mcp", "python", "-m", "recon_mcp"]
    },
    "stofs": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/stofs-mcp", "python", "-m", "stofs_mcp"]
    },
    "ofs": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/ofs-mcp", "python", "-m", "ofs_mcp"]
    },
    "rtofs": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/rtofs-mcp", "python", "-m", "rtofs_mcp"]
    },
    "ww3": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/ocean-mcp/servers/ww3-mcp", "python", "-m", "ww3_mcp"]
    }
  }
}
```

</details>

## Example Queries

With servers configured, you can ask your AI assistant naturally:

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

**Recon queries:**
- "List HDOB reconnaissance flights for the 2024 Atlantic season"
- "Get HDOB flight-level observations from October 7, 2024"
- "Show me the Vortex Data Messages for Hurricane Milton"
- "Get ATCF aircraft fix data for storm AL14 2024"

**STOFS queries:**
- "Get the STOFS water level forecast for The Battery, NY"
- "Compare STOFS forecast vs observations at Boston for the past 24 hours"
- "What are the top stations with highest predicted water levels?"
- "Find STOFS stations within 50 km of New Orleans"

**OFS queries:**
- "What OFS models cover the Chesapeake Bay?"
- "Get the water level forecast at lat 38.98, lon -76.48 from CBOFS"
- "Compare CBOFS water level with CO-OPS observations at station 8571892"
- "List available NGOFS2 forecast cycles for today"

**RTOFS queries:**
- "Get the RTOFS sea surface temperature forecast at 40°N, 74°W"
- "Show me a temperature depth profile in the Gulf Stream"
- "What RTOFS datasets are currently available on HYCOM THREDDS?"
- "Get a vertical transect of salinity from Miami to Bermuda"
- "Show the SST area forecast for the Gulf of Mexico"

**WW3 queries:**
- "What GFS-Wave model grids are available?"
- "Find NDBC buoys near Cape Hatteras"
- "Get the latest wave observations from buoy 41025"
- "Show me the GFS-Wave forecast at 35°N, 75°W for the next 48 hours"
- "Compare the wave forecast against buoy 41025 observations"

**Cross-server queries:**
- "Find CO-OPS stations near this ERDDAP buoy location"
- "Compare tide station data with nearby ERDDAP satellite SST"
- "Is there an active hurricane threatening the Gulf Coast? If so, show me the STOFS surge forecast for New Orleans"
- "Get the CBOFS water level forecast at Chesapeake Bay and compare it with the CO-OPS tide prediction for the same station"
- "Show me sea surface temperature from ERDDAP near The Battery and the current water level from CO-OPS"
- "Which NHC storms have hit the Gulf Coast historically? Show the CO-OPS flood statistics for impacted stations"
- "Get the STOFS gridded forecast and the OFS water level forecast at the same location and compare them"

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
  note      = {MCP servers for NOAA CO-OPS, ERDDAP, NHC, Recon, STOFS, OFS, RTOFS, and WW3 data}
}
```

## License

Licensed under the MIT License. You may use, modify, and distribute this software under the MIT terms. See [LICENSE](LICENSE) for details.
