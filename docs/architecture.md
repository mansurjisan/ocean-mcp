# Architecture

This document describes the stable, structural picture of the repo — how
servers are laid out, built, and shipped. It does **not** restate the
response/behavior contract (what `response_format` values exist, output
caps, error message shape, retry behavior, dependency bounds, etc.) — that
contract evolves and is described in one place only:
[CONVENTIONS.md](../CONVENTIONS.md). If you're implementing a tool, read
CONVENTIONS.md; this file is for understanding how the repo is put
together.

## Monorepo Pattern

Ocean-MCP uses a monorepo structure where each MCP server lives under
`servers/`. Each server is a fully independent Python package with its own
`pyproject.toml`, dependencies, source code, and tests.

```
ocean-mcp/
├── servers/
│   ├── coops-mcp/      # Independent package
│   ├── erddap-mcp/     # Independent package
│   └── nhc-mcp/        # Independent package
└── docs/
```

**No shared code between servers.** If two servers need the same utility
(e.g., a markdown table formatter), each has its own copy. This avoids
coupling and lets each server be developed, tested, and published
independently — there is intentionally no shared runtime package.

## Naming Convention

- **Python module**: `{source}_mcp` (e.g., `coops_mcp`, `erddap_mcp`)
- **Package name**: `{source}-mcp` (e.g., `coops-mcp`, `erddap-mcp`)
- **Tool prefix**: `{source}_` (e.g., `coops_get_water_levels`, `erddap_search_datasets`)

## Framework Stack

- **FastMCP** — MCP server framework with lifespan management
- **httpx** — async HTTP client for API calls, with a retrying transport
  (see CONVENTIONS.md's *HTTP resilience* section)
- **Pydantic** — request/response models; constrained tool parameters
  (like `response_format`) are typed as `Literal[...]`, not a bare `str` or
  a Pydantic enum, so the MCP tool schema advertises the allowed values as
  a JSON Schema `enum`

## Server Structure

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

## Lifespan Pattern

Each server creates an async HTTP client in the lifespan context, shared
across all tool calls:

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

## Tool Design Principles

1. **Read-only**: all tools are read-only with `readOnlyHint=True`. No data
   modification.
2. **`response_format` as `Literal[...]`**: every data tool takes a
   `response_format` parameter typed as a `Literal` of exactly the values it
   branches on. Across the repo this covers `markdown` (the default,
   human/LLM-readable, row-capped), `json` (a wrapped structured payload),
   `geojson` (station/track tools), and `image` (GOES imagery tools). See
   CONVENTIONS.md for the full breakdown and which servers use which
   subset.
3. **Output caps and truncation**: long series are capped rather than
   returned in full, with a truncation envelope in JSON and a footer note
   in markdown. See CONVENTIONS.md's *Output caps* section.
4. **Actionable errors**: each server has a `handle_<server>_error()` that
   distinguishes upstream API errors, HTTP status errors, and timeouts, and
   never returns a bare exception repr. See CONVENTIONS.md's *Error
   messages* section.

## Response Metadata

Wrapped JSON responses carry `retrieved_at` (UTC, tz-aware ISO 8601) plus
request context — units, datum, and timezone where applicable. This, along
with the exact wrapper shape, is defined in CONVENTIONS.md and is not
repeated here.

## Dependencies

Each server pins its own dependency versions independently (no shared lock
file). Direct dependencies carry major-version upper bounds so a future
major release can't silently break a standalone install; see
CONVENTIONS.md's *Dependencies* section for the specifics and exceptions.

## CI / Publish Pipeline

- **CI** (`.github/workflows/ci.yml`): a `detect-changes` job path-filters
  on `servers/<name>/**`, then `lint` (ruff, repo-wide) and a per-server
  `test` matrix run. PRs only run the matrix for servers that changed;
  pushes to `main` run all of them.
- **Publish**: each server is published to PyPI independently via GitHub
  OIDC trusted publishing (no long-lived tokens). Most servers also publish
  an entry to the MCP Registry as part of the same workflow.

## Server Independence

Each server can be:
- Installed independently: `cd servers/coops-mcp && uv sync`
- Tested independently: `uv run pytest tests/ -v`
- Deployed independently via `uvx coops-mcp`
- Used alone or alongside other servers in an MCP client config
