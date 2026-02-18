# CLAUDE.md — Ocean MCP: AI Tools for Ocean Science

## Project Overview

This is `ocean-mcp` — a monorepo containing multiple MCP (Model Context Protocol) servers for ocean science and coastal oceanography. Each server is independently installable and focuses on a specific data source or domain.

**Current servers:**
- `coops-mcp` — NOAA CO-OPS tides, water levels, currents, meteorological data (MIGRATED from existing standalone repo at ../CO-OPS-MCP-SERVER/)
- `erddap-mcp` — Universal ERDDAP data access across 80+ public servers (NEW — build this)
- `nhc-mcp` — NHC storm tracks, advisories, HURDAT2 best track data (NEW — scaffold only)

**Future servers (do NOT build yet, just reference in docs):**
- `schism-mcp` — SCHISM model config/namelist tools
- `stofs-mcp` — STOFS operational forecast products

---

## Monorepo Structure

```
ocean-mcp/
├── README.md                      # Umbrella README — project vision, server index, badges
├── LICENSE                        # MIT license
├── .gitignore
├── servers/
│   ├── coops-mcp/                 # MIGRATED from CO-OPS-MCP-SERVER repo
│   │   ├── README.md
│   │   ├── pyproject.toml
│   │   ├── src/coops_mcp/
│   │   │   ├── __init__.py
│   │   │   ├── __main__.py        # NEW — add this (was missing from original)
│   │   │   ├── server.py
│   │   │   ├── client.py
│   │   │   ├── models.py
│   │   │   ├── utils.py
│   │   │   └── tools/
│   │   │       ├── __init__.py
│   │   │       ├── stations.py
│   │   │       ├── water_levels.py
│   │   │       ├── meteorological.py
│   │   │       ├── currents.py
│   │   │       └── derived.py
│   │   ├── tests/
│   │   └── eval/
│   │
│   ├── erddap-mcp/               # NEW — build this fully
│   │   ├── README.md
│   │   ├── pyproject.toml
│   │   ├── src/erddap_mcp/
│   │   │   ├── __init__.py
│   │   │   ├── __main__.py
│   │   │   ├── server.py
│   │   │   ├── client.py
│   │   │   ├── models.py
│   │   │   ├── utils.py
│   │   │   ├── registry.py        # Known ERDDAP server registry
│   │   │   └── tools/
│   │   │       ├── __init__.py
│   │   │       ├── search.py       # Dataset discovery & search
│   │   │       ├── griddap.py      # Gridded data access
│   │   │       ├── tabledap.py     # Tabular data access
│   │   │       └── metadata.py     # Dataset metadata & info
│   │   ├── tests/
│   │   └── eval/
│   │
│   └── nhc-mcp/                   # NEW — scaffold structure + README only
│       ├── README.md
│       ├── pyproject.toml
│       └── src/nhc_mcp/
│           ├── __init__.py
│           └── server.py           # Minimal placeholder
│
└── docs/
    └── architecture.md            # How the servers relate, shared patterns
```

---

## Step-by-Step Implementation Order

### Phase 1: Create monorepo and migrate CO-OPS

1. Initialize the `ocean-mcp/` directory structure
2. Copy the entire CO-OPS MCP server code from `../CO-OPS-MCP-SERVER/` into `servers/coops-mcp/`
3. Apply these fixes to the migrated CO-OPS code:
   - Add `src/coops_mcp/__main__.py` with contents: `from .server import main` and `main()`
   - In ALL tool files, verify the lifespan context access pattern works. The helper should be:
     ```python
     def _get_client(ctx: Context) -> COOPSClient:
         return ctx.request_context.lifespan_context["coops_client"]
     ```
     If the installed MCP SDK version uses `lifespan_state` instead of `lifespan_context`, update accordingly.
   - In `derived.py` `coops_get_extreme_water_levels`: include the actual water level VALUES in the output, not just dates and status
   - In `derived.py` `coops_get_peak_storm_events`: pass `datum` and `units` params to the API call
   - Fix the clone URL in `servers/coops-mcp/README.md` to point to the monorepo
4. Create root `LICENSE` file (MIT)
5. Create root `.gitignore` (Python standard)

### Phase 2: Build ERDDAP MCP Server (MAIN TASK)

See the detailed ERDDAP specification below. Build it fully with all 6 tools.

### Phase 3: Scaffold NHC MCP Server

Create the directory structure and a README describing the planned tools, but only implement a minimal `server.py` placeholder.

### Phase 4: Create umbrella README and docs

Write the root `README.md` and `docs/architecture.md`.

---

## ERDDAP MCP Server — Detailed Specification

### What it does

Provides AI assistants with the ability to discover, search, and retrieve data from any ERDDAP server worldwide. ERDDAP is the backbone of ocean data distribution — NOAA CoastWatch, IOOS regional associations, Copernicus, and 80+ institutions run ERDDAP servers. **No API key required.**

### ERDDAP API Reference

ERDDAP has a simple REST API pattern: `{server_url}/erddap/{protocol}/{datasetID}.{fileType}?{query}`

**Two data protocols:**

1. **tabledap** — for tabular/in-situ data (buoys, gliders, ship tracks, profiles)
   - URL: `{server}/erddap/tabledap/{datasetID}.json?{variables}&{constraints}`
   - Constraints: `variable>=value`, `variable<=value`, `variable="value"`
   - Example: `https://coastwatch.pfeg.noaa.gov/erddap/tabledap/cwwcNDBCMet.json?station,time,wtmp,atmp&time>=2024-01-01&time<=2024-01-31&station="46013"`

2. **griddap** — for gridded/satellite data (SST, chlorophyll, currents, winds)
   - URL: `{server}/erddap/griddap/{datasetID}.json?{variable}[({dim1_start}):({stride}):({dim1_stop})][...]`
   - Dimensions typically: [time][latitude][longitude] or [time][altitude][latitude][longitude]
   - Example: `https://coastwatch.pfeg.noaa.gov/erddap/griddap/erdMH1chlamday.json?chlorophyll[(2024-01-15T00:00:00Z)][(36):(38)][(-123):(-121)]`

**Discovery endpoints:**
- Search: `{server}/erddap/search/index.json?searchFor={terms}&page=1&itemsPerPage=100`
- All datasets: `{server}/erddap/tabledap/allDatasets.json?datasetID,title,summary,institution`
- Dataset info: `{server}/erddap/info/{datasetID}/index.json`

**ERDDAP JSON response format** (important — not standard):
```json
{
  "table": {
    "columnNames": ["time", "latitude", "longitude", "sst"],
    "columnTypes": ["String", "float", "float", "float"],
    "columnUnits": ["UTC", "degrees_north", "degrees_east", "degree_C"],
    "rows": [
      ["2024-01-15T00:00:00Z", 37.0, -122.0, 12.5]
    ]
  }
}
```

### ERDDAP Server Registry (registry.py)

Hardcode a dict of well-known ERDDAP servers. Include at minimum:

| Name | URL | Focus |
|------|-----|-------|
| CoastWatch West Coast | `https://coastwatch.pfeg.noaa.gov/erddap` | Satellite, SST, chlorophyll |
| CoastWatch CWHDF | `https://cwcgom.aoml.noaa.gov/erddap` | Gulf of Mexico |
| IOOS Gliders | `https://gliders.ioos.us/erddap` | Underwater glider data |
| NCEI | `https://www.ncei.noaa.gov/erddap` | Climate/archive data |
| OSMC | `https://osmc.noaa.gov/erddap` | Observing system monitoring |
| NERACOOS | `https://www.neracoos.org/erddap` | NE US regional ocean obs |
| PacIOOS | `https://pae-paha.pacioos.hawaii.edu/erddap` | Pacific Islands |
| BCO-DMO | `https://erddap.bco-dmo.org/erddap` | Bio/chemical ocean data |
| NOAA UAF | `https://upwell.pfeg.noaa.gov/erddap` | Fisheries, upwelling |
| OOI | `https://erddap.dataexplorer.oceanobservatories.org/erddap` | Ocean Observatories Initiative |
| SECOORA | `https://erddap.secoora.org/erddap` | SE US regional ocean obs |

Add a function `get_servers(region=None, keyword=None)` that filters and returns matching servers.

### ERDDAP Tools to Implement (6 tools)

#### `erddap_list_servers`
List known ERDDAP servers from the built-in registry.
- Inputs: `region` (optional), `keyword` (optional filter)
- Annotations: readOnly=True, destructive=False, idempotent=True, openWorld=False

#### `erddap_search_datasets`
Search for datasets on an ERDDAP server using free-text search.
- Inputs: `search_for` (required), `server_url` (optional, default CoastWatch), `protocol` (optional: griddap/tabledap), `items_per_page` (default 20), `page` (default 1)
- Implementation: GET `{server}/erddap/search/index.json?searchFor={terms}&page={page}&itemsPerPage={n}`
- Annotations: readOnly=True, destructive=False, idempotent=True, openWorld=True

#### `erddap_get_dataset_info`
Get detailed metadata for a dataset — variables, dimensions, attributes, time/spatial coverage.
- Inputs: `server_url` (required), `dataset_id` (required)
- Implementation: GET `{server}/erddap/info/{datasetID}/index.json`
- Annotations: readOnly=True, destructive=False, idempotent=True, openWorld=True

#### `erddap_get_tabledap_data`
Retrieve tabular data with constraint filtering.
- Inputs: `server_url`, `dataset_id`, `variables` (optional list), `constraints` (optional dict, e.g., `{"time>=": "2024-01-01", "latitude>=": 38.0}`), `limit` (default 1000), `response_format` (markdown/json)
- Build URL: `{server}/erddap/tabledap/{id}.json?{vars}&{constraints}`
- Validate: warn if no constraints (could return huge data). Suggest `erddap_get_dataset_info` first.
- Annotations: readOnly=True, destructive=False, idempotent=True, openWorld=True

#### `erddap_get_griddap_data`
Retrieve gridded data with dimension subsetting.
- Inputs: `server_url`, `dataset_id`, `variables` (optional), `time_range` (optional [start, stop]), `latitude_range` (optional [min, max]), `longitude_range` (optional [min, max]), `depth_range` (optional [min, max]), `stride` (default 1), `response_format`
- Build griddap URL with bracket notation for dimension subsetting
- Must internally query dataset info to determine dimension order
- Validate: warn about large requests, suggest increasing stride
- Annotations: readOnly=True, destructive=False, idempotent=True, openWorld=True

#### `erddap_get_all_datasets`
List all datasets on a specific ERDDAP server.
- Inputs: `server_url`, `protocol` (optional filter), `institution` (optional filter), `search_text` (optional filter), `limit` (default 50), `offset` (default 0)
- Implementation: GET `{server}/erddap/tabledap/allDatasets.json?datasetID,title,summary,institution,...`
- Annotations: readOnly=True, destructive=False, idempotent=True, openWorld=True

### ERDDAP Client (client.py)

Async httpx client with methods: `search()`, `get_info()`, `get_tabledap()`, `get_griddap()`, `get_all_datasets()`, `close()`. Use `timeout=60.0` (ERDDAP can be slow), `follow_redirects=True`. Handle ERDDAP errors which sometimes come as HTML rather than JSON.

### ERDDAP Utils (utils.py)

- `parse_erddap_json(data: dict) -> list[dict]` — convert ERDDAP's `{"table": {"columnNames": [...], "rows": [...]}}` into a list of row dicts
- `format_erddap_table(data, columns, title, ...)` — markdown table formatter
- `build_tabledap_query(variables, constraints, limit)` — construct tabledap URL query string
- `build_griddap_query(variable, dimensions: dict)` — construct griddap bracket notation
- `handle_erddap_error(e)` — error handler with actionable suggestions

### ERDDAP pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "erddap-mcp"
version = "0.1.0"
description = "MCP server for accessing ocean data from ERDDAP servers worldwide"
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
dependencies = [
    "mcp[cli]>=1.0.0",
    "httpx>=0.27.0",
    "pydantic>=2.0.0",
]

[project.scripts]
erddap-mcp = "erddap_mcp.server:main"

[tool.hatch.build.targets.wheel]
packages = ["src/erddap_mcp"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[dependency-groups]
dev = ["pytest>=8.0.0", "pytest-asyncio>=0.24.0", "respx>=0.22.0"]
```

### ERDDAP Tests

**Live integration tests** (`tests/test_live.py`):
1. Search CoastWatch for "sea surface temperature" → returns results
2. Get info for dataset `erdMH1chlamday` on CoastWatch → returns variables
3. Get tabledap data from NDBC buoy dataset → returns rows
4. List all datasets on CoastWatch → returns 100+ datasets
5. Get small griddap data subset → returns grid values

### ERDDAP Evaluation (eval/evaluation.xml)

10 questions testing multi-tool usage:
1. "How many griddap datasets are available on CoastWatch West Coast?"
2. "What variables are in the MUR SST dataset (jplMURSST41) on CoastWatch?"
3. "Find chlorophyll datasets on the NCEI ERDDAP server"
4. "What is the time range for NDBC met buoy data on CoastWatch?"
5. "List all ERDDAP servers focused on the US East Coast"
6. "What institution provides the most datasets on IOOS Gliders ERDDAP?"
7. "Get latest SST from MUR SST at lat 37, lon -122"
8. "What is the spatial coverage of HYCOM on NCEI ERDDAP?"
9. "Search for wind speed datasets on OSMC"
10. "How many tabledap vs griddap datasets are on PacIOOS?"

---

## NHC MCP Server — Scaffold Only

Create directory structure with `README.md` listing planned tools (marked "Coming Soon"):
- `nhc_get_active_storms`, `nhc_get_forecast_track`, `nhc_get_best_track`
- `nhc_search_storms`, `nhc_get_storm_surge_watch`, `nhc_generate_parametric_wind`

Data sources to document: NHC ATCF feeds, HURDAT2, IBTrACS, NHC RSS feeds.

Minimal `server.py`:
```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("nhc_mcp")
def main():
    mcp.run()
if __name__ == "__main__":
    main()
```

---

## Root README.md

Include: project title ("🌊 Ocean MCP — AI Tools for Ocean Science"), server index table with status badges (✅ Ready / 🚧 Planned), quick start showing Claude Code config for multiple servers, example queries demonstrating cross-server use, contributing guidelines, author info (Mansur Ali Jisan, NOAA NOS CO-OPS).

## docs/architecture.md

Document: monorepo pattern, shared conventions (FastMCP + httpx + Pydantic, read-only tools, dual markdown/JSON output, actionable error messages), server independence (each has own pyproject.toml), naming convention (`{source}_mcp` module / `{source}-mcp` package).

---

## Important Notes

- **No shared code between servers.** Each is fully self-contained. If both need a markdown table formatter, each has its own. This avoids coupling.
- **ERDDAP URLs must be carefully constructed.** tabledap uses ampersand-separated constraints, griddap uses bracket notation. Test URL building thoroughly.
- **ERDDAP servers vary in reliability.** Use `follow_redirects=True`, timeout=60s. Suggest alternative servers in errors.
- **Griddap dimension order matters.** Always query dataset info first to determine dimension order before building queries.
- **Keep responses concise.** Limit data returns to reasonable sizes (1000 rows tabledap, small spatial subsets griddap). Include counts, suggest further constraints for large datasets.
- **ERDDAP errors often come as HTML.** Detect non-JSON responses and extract error messages.
