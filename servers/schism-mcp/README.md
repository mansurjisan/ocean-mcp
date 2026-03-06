# schism-mcp

<!-- mcp-name: io.github.mansurjisan/schism-mcp -->

MCP server for SCHISM model setup debugging, parameter lookup, and configuration validation.

Unlike the other ocean-mcp servers that query remote NOAA APIs, schism-mcp **parses local model input files** and provides **embedded domain knowledge** to help debug and understand SCHISM configurations.

## Tools (10)

### Parameter Reference
- **`schism_explain_parameter`** — Look up any param.nml parameter, tidal constituent, vertical grid type, or BC type
- **`schism_list_parameters`** — List all parameters grouped by section (CORE, OPT, SCHOUT)

### File Parsing
- **`schism_parse_param_nml`** — Parse FORTRAN namelist file into structured summary
- **`schism_parse_hgrid`** — Parse hgrid.gr3 header (node/element counts, bounding box, boundaries)
- **`schism_parse_vgrid`** — Parse vgrid.in (LSC2/SZ type, level count, layer distribution)
- **`schism_parse_bctides`** — Parse bctides.in (tidal constituents, boundary segments)

### Validation & Debugging
- **`schism_validate_config`** — Comprehensive validation with cross-file checks
- **`schism_diagnose_error`** — Match error text against known SCHISM failure patterns

### Documentation
- **`schism_fetch_docs`** — Fetch pages from the SCHISM documentation site
- **`schism_search_docs`** — Search SCHISM documentation

## Installation

```bash
# Using uvx (recommended)
uvx schism-mcp

# Or install from source
cd servers/schism-mcp
uv sync
```

## Configuration

Add to your MCP client config:

```json
{
  "mcpServers": {
    "schism": {
      "command": "uvx",
      "args": ["schism-mcp"]
    }
  }
}
```

## Development

```bash
cd servers/schism-mcp
uv sync --group dev
uv run pytest tests/ --ignore=tests/test_live.py --ignore=tests/test_mcp_protocol.py -v
```

## License

MIT
