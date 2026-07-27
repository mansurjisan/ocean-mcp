# nos-workflow-mcp

**Experimental / work in progress.** This server is not published to PyPI
and is not ready for general use. `main` carries only a minimal subset of
the intended functionality — the real implementation lives on an unmerged
branch. It's also excluded from CI. Expect breaking changes without notice;
don't build on it yet.

MCP server for NOAA's NOS Operational Forecast System (OFS) workflow management. Provides tools for reading OFS configurations, comparing systems, diagnosing run failures, and monitoring ecFlow suites.

Supports all NOS OFS systems: STOFS-3D-ATL, STOFS-3D-PAC, SECOFS, CREOFS, CBOFS, DBOFS, LEOFS, NGOFS2.

## Tools

| Tool | Description |
|------|-------------|
| `nos_list_systems` | List all available OFS systems with model type and framework |
| `nos_get_config` | Read full YAML configuration for any OFS system |
| `nos_compare_configs` | Compare two OFS systems side by side |
| `nos_diagnose_failure` | Parse log/fatal.error files and classify the failure |
| `nos_get_ecflow_suite` | Show ecFlow task dependency tree for a system/cycle |
| `nos_get_ensemble_config` | Show ensemble configuration (members, perturbation params) |

## Installation

```bash
pip install -e .
```

## Configuration

Set `NOS_WORKFLOW_DIR` to the path of the nos-workflow repository:

```bash
export NOS_WORKFLOW_DIR=/path/to/nos-workflow
```
