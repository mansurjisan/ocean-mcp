# CLAUDE.md — Ocean-MCP Project Guidelines

## Project Overview

Ocean-MCP is a monorepo of 6 independently installable MCP servers for NOAA ocean data. Each server lives in `servers/<name>/` with its own `pyproject.toml`, source code, and (soon) tests.

Servers: `coops-mcp`, `erddap-mcp`, `nhc-mcp`, `recon-mcp`, `stofs-mcp`, `ofs-mcp`

Stack: FastMCP, httpx (async), Pydantic, Python 3.10+. All servers are read-only. All use free public NOAA APIs (no keys needed).

## Current Task: Add Automated Tests

### Step 1: Discover each server's tools and structure

Before writing any tests, read the source code of ALL 6 servers. For each server:
- Identify every `@mcp.tool()` decorated function and its signature
- Identify Pydantic input models and their validation rules
- Identify HTTP endpoints called (the NOAA API URLs)
- Note the response format (markdown and/or JSON output)

### Step 2: Create test infrastructure

**Per-server test directory:**
```
servers/<name>/tests/
├── __init__.py
├── conftest.py           # fixtures, httpx mocks, fixture loader
├── fixtures/             # saved JSON responses from NOAA APIs
├── test_tools.py         # unit tests (mocked HTTP)
├── test_validation.py    # Pydantic input validation tests
├── test_integration.py   # live API tests (marked @pytest.mark.integration)
└── test_mcp_protocol.py  # MCP client session tests
```

**Root-level pytest config** — create `pytest.ini` in the repo root:
```ini
[pytest]
asyncio_mode = auto
markers =
    integration: tests that hit live NOAA APIs (deselect with '-m "not integration"')
testpaths = servers
```

**Dev dependencies** — add to each server's `pyproject.toml`:
```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-httpx>=0.30",
]
```

### Step 3: Create JSON fixtures

For each server, call the real NOAA API once and save the response as a fixture file. Examples for coops-mcp:

```bash
curl -s "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?date=latest&station=8518750&product=water_level&datum=MLLW&time_zone=gmt&units=metric&format=json" > servers/coops-mcp/tests/fixtures/water_levels.json
curl -s "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?begin_date=20250101&end_date=20250102&station=8518750&product=predictions&datum=MLLW&time_zone=gmt&units=metric&interval=hilo&format=json" > servers/coops-mcp/tests/fixtures/tide_predictions.json
curl -s "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/8518750.json" > servers/coops-mcp/tests/fixtures/station_metadata.json
```

Do the equivalent for all 6 servers using their respective API endpoints. Inspect each server's source to find the exact URLs and parameters.

### Step 4: Write tests — 3 tiers

**Tier 1: Unit tests** (`test_tools.py`, `test_validation.py`) — mock all HTTP, no network:

- Tool registration: verify all `@mcp.tool` functions are registered
- Input validation: verify Pydantic models reject invalid inputs (bad station IDs, invalid date ranges, out-of-range coordinates, etc.)
- Response parsing: use pytest-httpx to mock httpx calls with fixture JSON, verify tools parse and format output correctly
- Error handling: mock HTTP 404, 500, timeouts — verify tools return helpful error messages, not stack traces

Minimum 5 unit tests per server.

**Tier 2: Integration tests** (`test_integration.py`) — hit real NOAA APIs:

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_battery_water_levels():
    """Fetch real water levels from The Battery, NYC."""
    # Call the actual tool function with real parameters
    # Assert non-empty, sensible result
```

Well-known test targets:
- coops-mcp: Station 8518750 (The Battery, NYC)
- erddap-mcp: CoastWatch ERDDAP dataset search
- nhc-mcp: HURDAT2 search for Hurricane Katrina (AL122005)
- recon-mcp: A known historical HDOB flight
- stofs-mcp: STOFS forecast for The Battery
- ofs-mcp: CBOFS model data

Minimum 2 integration tests per server. Use `continue-on-error` tolerance for API flakiness.

**Tier 3: MCP protocol tests** (`test_mcp_protocol.py`) — verify MCP server lifecycle:

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_mcp_server_starts_and_lists_tools():
    server_params = StdioServerParameters(
        command="python", args=["-m", "<module_name>"]
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert len(tools.tools) > 0
```

1 protocol test per server.

### Step 5: GitHub Actions CI

Create `.github/workflows/test.yml`:

```yaml
name: Tests
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
        server: [coops-mcp, erddap-mcp, nhc-mcp, recon-mcp, stofs-mcp, ofs-mcp]

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - uses: astral-sh/setup-uv@v3

      - name: Install dependencies
        working-directory: servers/${{ matrix.server }}
        run: |
          uv sync
          uv pip install ".[dev]"

      - name: Run unit tests
        working-directory: servers/${{ matrix.server }}
        run: uv run pytest tests/ -v -m "not integration" --tb=short

      - name: Run integration tests (main branch only)
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        working-directory: servers/${{ matrix.server }}
        run: uv run pytest tests/ -v -m integration --tb=short
        continue-on-error: true
```

### Verification

After all tests are written, confirm:

```bash
# All unit tests pass (no network)
pytest servers/ -m "not integration" -v

# Per-server
cd servers/coops-mcp && pytest tests/ -m "not integration" -v

# Integration tests (needs network)
pytest servers/ -m integration -v
```

## Code Style

- Every test function must have a docstring
- Use `snake_case` for test names: `test_get_water_levels_returns_data`
- Group related tests in classes if there are many per tool
- Keep fixtures minimal — only the fields the tool actually uses
- Integration tests must use reasonable timeouts and handle API slowness gracefully

## Repo Hygiene Note

The root directory currently has loose demo scripts and output files (`.py`, `.json`, `.png`). These should eventually be moved to `examples/` or `demos/` but that is NOT part of this task — focus only on tests.
