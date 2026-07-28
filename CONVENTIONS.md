# Conventions

Cross-server response and behavior conventions for the ocean-mcp servers.

These servers are **independently installable and published — there is no shared
runtime package, by design.** Consistency is therefore maintained by *copying the
pattern* and following this document, **not** by a shared dependency. When you add
or change a tool, match the conventions below; when you find a better pattern,
update this doc and propagate it per-server.

---

## `response_format`

Every data tool takes `response_format: Literal[...] = "markdown"` — a `Literal`,
never a bare `str`, so the MCP tool schema advertises an `enum` and clients
validate the argument up front.

| value | meaning |
|-------|---------|
| `markdown` (default) | human/LLM-readable; tables are **capped** (see *Output caps*) with a footer noting any truncation |
| `json` | structured payload in a **wrapper** (see *JSON response wrappers*) |
| `geojson` | RFC 7946 FeatureCollection (station/track tools only) |
| `image` | embedded JPEG (GOES imagery tools only; their default) |

The `Literal` must list **exactly** the values that tool branches on — no more, no
less. A `Literal` is *not* enforced on direct Python calls (only at the MCP
boundary), so unit tests won't catch a too-narrow list; verify with the tool's
`inputSchema['properties']['response_format']['enum']` via `mcp.list_tools()`.

## Output caps (token discipline)

A long series can be tens of thousands of records and will flood the model's
context, so output is capped:

- **JSON**: a `max_records` / `max_points` / `max_rows` parameter (default `2000`)
  plus a truncation envelope.
- **Markdown**: a bounded number of rows plus a footer — `*Showing N of M …*`.

The envelope carries `truncated` (bool), a **returned-count**, a **total**, and a
`hint` when truncated. Which end is kept follows the source's record order:
**oldest-first** sources keep the tail (most recent); **newest-first** keep the
head; **order-unspecified** keep the head (matching how the upstream `limit`
truncates). Verify ordering against the live API before choosing — don't assume.

## JSON response wrappers

A wrapped JSON response carries top-level metadata alongside the data:

- **`retrieved_at`** — when the data was fetched, as
  `datetime.now(timezone.utc).isoformat(timespec="seconds")` (ISO 8601, UTC,
  tz-aware, e.g. `2026-05-25T20:50:34+00:00`).
- the truncation envelope fields (above).
- request context: station id / params, and **units, datum, timezone** where
  applicable (these may be nested under a `request_params`/`metadata` key — don't
  drop them).

Reference wrappers: `coops`/`recon` `format_json_response`, `usgs` `_cap_waterml`,
`ndbc` `_capped_obs_json`, `erddap` `cap_rows`. Tools that emit a bare list or an
unwrapped metadata dump are not "wrappers"; add a wrapper if a tool grows enough
metadata to warrant one.

## Response metadata

Water-level responses must state their **datum**; all responses should state
**units**, **timezone** (UTC/GMT is the default), the **source**, and the
**cycle/issuance time** where the data is forecast/model output. The goal is that a
value is never ambiguous about its reference frame.

## Error messages

Each server has a `handle_<server>_error(e)` that returns
`"<Server> Error: <what went wrong> — <concrete next step>"`. It distinguishes the
server's API error, `httpx.HTTPStatusError`, and `httpx.TimeoutException`, and
falls back to a typed generic. **Never return a bare exception repr.** Optional
augmentations (e.g. an enrichment lookup) degrade to `None` rather than failing the
whole tool.

## HTTP resilience

Each client mounts a `RetryTransport(httpx.AsyncHTTPTransport)` on its
`httpx.AsyncClient`: it retries **idempotent GETs** on `httpx.TransportError`
(connect + read/timeouts) and transient responses `{429, 500, 502, 503, 504}` with
exponential backoff + jitter, re-raising the original exception when retries are
exhausted. The client `__init__` exposes `max_retries=2, backoff_factor=0.5`. It is
copied per server (no shared module). Non-GET requests and non-transient responses
pass straight through.

## GeoJSON

FeatureCollection; coordinates are **`[lon, lat]`** (RFC 7946 order — there are
tests pinning this); `LineString` for tracks (only when ≥2 points), `Point` for
stations; skip features with null coordinates.

## Dependencies

Direct dependencies carry **major-version upper bounds** (e.g. `mcp<2`,
`pydantic<3`, `numpy<3`, `httpx<1`) so a future major release can't silently break
a standalone install. CalVer dependencies (e.g. `xarray`) are left uncapped — they
have no meaningful "next major". Git dependencies are pinned to a **commit SHA**.

## Testing

- Mock HTTP with `respx` or `pytest-httpx` (follow the server's existing choice).
- `test_live.py` hits real APIs and is **CI-ignored**; `test_tools.py` /
  `test_validation.py` are the mocked unit tests; `test_mcp_protocol.py` spawns the
  server over stdio with `command=sys.executable, args=["-m", "<module>"]`.
- `asyncio_mode = "auto"`.
- Construct test clients with `backoff_factor=0` so `RetryTransport` replays
  transient-failure mocks instantly (otherwise those tests sleep for real).
