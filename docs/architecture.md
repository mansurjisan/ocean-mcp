# Architecture

## Monorepo Pattern

Ocean MCP uses a monorepo structure where each MCP server lives under `servers/`. Each server is a fully independent Python package with its own `pyproject.toml`, dependencies, source code, tests, and evaluation suite.

```
ocean-mcp/
├── servers/
│   ├── coops-mcp/      # Independent package
│   ├── erddap-mcp/     # Independent package
│   └── nhc-mcp/        # Independent package
└── docs/
```

**No shared code between servers.** If two servers need the same utility (e.g., a markdown table formatter), each has its own copy. This avoids coupling and ensures each server can be developed, tested, and deployed independently.

## Naming Convention

- **Python module**: `{source}_mcp` (e.g., `coops_mcp`, `erddap_mcp`)
- **Package name**: `{source}-mcp` (e.g., `coops-mcp`, `erddap-mcp`)
- **Tool prefix**: `{source}_` (e.g., `coops_get_water_levels`, `erddap_search_datasets`)

## Shared Conventions

While servers don't share code, they follow the same architectural patterns:

### Framework Stack

- **FastMCP** — MCP server framework with lifespan management
- **httpx** — Async HTTP client for API calls
- **Pydantic** — Enum-based parameter validation

### Server Structure

Each server follows this layout:

```
src/{source}_mcp/
├── __init__.py      # Package docstring
├── __main__.py      # Entry point: from .server import main; main()
├── server.py        # FastMCP instance, lifespan, tool registration
├── client.py        # Async HTTP client for the data source API
├── models.py        # Pydantic models and enums
├── utils.py         # Formatters, error handlers, helpers
└── tools/
    ├── __init__.py
    └── *.py         # One file per tool category
```

### Tool Design Principles

1. **Read-only**: All tools are read-only with `readOnlyHint=True`. No data modification.
2. **Dual output**: Tools support both `markdown` (default) and `json` response formats.
3. **Actionable errors**: Error messages include specific suggestions (e.g., "Use erddap_get_dataset_info to check available variables").
4. **Reasonable defaults**: Limit data returns to sensible sizes (1000 rows for tabledap, small spatial subsets for griddap).
5. **Parameter validation**: Use Pydantic enums for constrained parameters.

### Lifespan Pattern

Each server creates an async HTTP client in the lifespan context, shared across all tool calls:

```python
@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    client = MyClient()
    try:
        yield {"my_client": client}
    finally:
        await client.close()

mcp = FastMCP("my_mcp", lifespan=app_lifespan)
```

Tools access the client via:

```python
def _get_client(ctx: Context) -> MyClient:
    return ctx.request_context.lifespan_context["my_client"]
```

### Error Handling

Each server has a `handle_*_error()` function in `utils.py` that:
- Detects HTTP status errors, timeouts, and connection errors
- Extracts error messages from non-JSON responses (ERDDAP returns HTML errors)
- Provides actionable suggestions specific to the data source

## Server Independence

Each server can be:
- Installed independently: `cd servers/coops-mcp && uv sync`
- Tested independently: `uv run pytest tests/ -v`
- Deployed independently via `uvx coops-mcp`
- Used alone or alongside other servers in MCP client config
