# adcirc-mcp

MCP server for ADCIRC model setup debugging, parameter lookup, and configuration validation.

Unlike the other ocean-mcp servers that query remote NOAA APIs, adcirc-mcp **parses local model input files** and provides **embedded domain knowledge** to help debug and understand ADCIRC configurations.

## Tools (10)

### Parameter Reference
- **`adcirc_explain_parameter`** — Look up any fort.15 parameter, NWS value, tidal constituent, or nodal attribute
- **`adcirc_list_parameters`** — List all parameters grouped by category

### File Parsing
- **`adcirc_parse_fort15`** — Parse fort.15 control file into structured summary
- **`adcirc_parse_fort14`** — Parse fort.14 mesh file header (node/element counts, boundaries)
- **`adcirc_parse_fort13`** — Parse fort.13 nodal attributes (names, defaults, non-default counts)
- **`adcirc_parse_fort22`** — Parse fort.22 meteorological forcing header

### Validation & Debugging
- **`adcirc_validate_config`** — Comprehensive validation with CFL check and cross-file verification
- **`adcirc_diagnose_error`** — Match error text against known ADCIRC failure patterns

### Documentation
- **`adcirc_fetch_docs`** — Fetch pages from the ADCIRC wiki
- **`adcirc_search_docs`** — Search the ADCIRC wiki

## Installation

```bash
# Using uvx (recommended)
uvx adcirc-mcp

# Or install from source
cd servers/adcirc-mcp
uv sync
```

## Configuration

Add to your MCP client config:

```json
{
  "mcpServers": {
    "adcirc": {
      "command": "uvx",
      "args": ["adcirc-mcp"]
    }
  }
}
```

## Development

```bash
cd servers/adcirc-mcp
uv sync --group dev
uv run pytest tests/ --ignore=tests/test_live.py --ignore=tests/test_mcp_protocol.py -v
```

## License

MIT
