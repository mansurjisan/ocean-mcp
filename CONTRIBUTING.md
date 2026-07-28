# Contributing to Ocean-MCP

Ocean-MCP is a monorepo of independently installable MCP servers under
`servers/<name>/`, each with its own `pyproject.toml`, `src/<module>/`, and
`tests/`. There is intentionally no shared runtime package, so cross-server
consistency is maintained by convention rather than by shared code — read
[CONVENTIONS.md](CONVENTIONS.md) before writing a new tool or server; it's
the authoritative reference for `response_format` enums, output caps and
truncation, `retrieved_at`, error-message style, HTTP retries, GeoJSON, and
dependency version bounds. New tools should match that pattern, not invent a
new shape.

## Scope

**One concern per PR, scoped to a single server.** Don't bundle unrelated
fixes across multiple servers into one PR — it makes review and CI failures
harder to attribute.

`servers/nos-workflow-mcp` is an active work-in-progress: its real
implementation lives on an unmerged branch, and `main` carries only a
minimal subset. It's excluded from CI and out of scope for outside
contributions unless a maintainer says otherwise.

## Workflow

1. **Branch from fresh `origin/main`:**

   ```bash
   git fetch origin
   git checkout -b <type>/<slug> origin/main
   ```

2. **Implement + tests.** Every test has a docstring, uses `snake_case`
   names, and is grouped in classes. Keep fixtures minimal. Mock HTTP with
   `respx` or `pytest-httpx` — follow whichever the server already uses.

3. **Lint exactly as CI does** (ruff is pinned to `0.15.2`; both checks must
   pass):

   ```bash
   ruff check servers/ --select E,F,W --ignore E501
   ruff format --check servers/
   ```

4. **Verify the changed server the way CI will:**

   ```bash
   cd servers/<name>
   uv sync --group dev
   uv run pytest tests/ --ignore=tests/test_live.py
   uv build
   ```

   `test_live.py` hits real upstream APIs and is intentionally excluded from
   this run (and from CI) — see *Testing conventions* below.

5. **Commit with a file, not an inline message:**

   ```bash
   git commit -F <message-file>
   ```

   This avoids shell backtick/`$()` substitution mangling commit messages.
   Push your branch and open a PR.

6. **Poll CI, then squash-merge `--delete-branch` once it's green.**

No AI attribution anywhere — no "Generated with...", no `Co-Authored-By`,
in commits, PR titles/descriptions, or issues.

### `gh pr edit` doesn't work here

`gh pr edit` fails on this repo due to the GitHub Projects-classic GraphQL
deprecation. To edit a PR's title or body, use:

```bash
gh api -X PATCH repos/<owner>/<repo>/pulls/<number> -f title="..." -F body=@body-file.md
```

## Testing conventions

Per server, tests are laid out as:

- `test_tools.py` / `test_validation.py` — unit tests, HTTP mocked.
- `test_live.py` — hits real upstream APIs; excluded from CI and from the
  `pytest` invocation above.
- `test_mcp_protocol.py` — spawns the server over stdio and exercises it as
  an MCP client would. Use `command=sys.executable, args=["-m", "<module>"]`
  — not `"python"` — so it runs the same interpreter as the test process.

`asyncio_mode = "auto"` is set per server; async tests don't need an
explicit marker.

## What CI actually runs

`.github/workflows/ci.yml` has three stages: `detect-changes` (path-filters
on `servers/<name>/**`) → `lint` → the `test` matrix. On a PR, only servers
whose files changed run in the matrix; on push to `main`, all servers run.
A change touching only `examples/`, docs, or the repo root triggers no
server job at all — that's expected, not a CI failure.

## Adding a new server or tool

Match [CONVENTIONS.md](CONVENTIONS.md) rather than improvising:

- `response_format` is a `Literal[...]`, never a bare `str`, listing exactly
  the values the tool branches on (`markdown`, `json`, and — where
  applicable — `geojson` or `image`).
- Long series get output caps with a truncation envelope, both in JSON
  (`max_records`/`max_points`/`max_rows`, default `2000`) and in markdown
  (a row cap plus a `*Showing N of M …*` footer).
- Wrapped JSON responses carry `retrieved_at` (UTC, tz-aware ISO 8601),
  the truncation envelope, and request context (units, datum, timezone
  where relevant).
- Errors go through a `handle_<server>_error(e)` that returns
  `"<Server> Error: <what went wrong> — <concrete next step>"` — never a
  bare exception repr.
- Each client mounts a `RetryTransport` on its `httpx.AsyncClient` for
  retryable GETs.
- Direct dependencies carry major-version upper bounds (`mcp<2`,
  `pydantic<3`, `httpx<1`, etc.); CalVer dependencies like `xarray` are left
  uncapped; git dependencies are pinned to a commit SHA.

If you find a better pattern than what's in CONVENTIONS.md, update that doc
alongside your change and note in the PR which other servers should pick it
up.

## Verify before you "fix"

Static review of parsing/format logic in this repo has produced false
"bugs" before (missing values that looked numeric but were sentinel
strings, an unpadded field that looked malformed but wasn't). Before
changing parsing or format logic, fetch the real upstream API and confirm
the actual shape — don't assume from reading the code alone. After fixing,
verify end-to-end against live data, not just mocks.
