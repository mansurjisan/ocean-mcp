# UFS Runner MCP

MCP server for setting up, validating, submitting, and monitoring UFS-Coastal experiments on NOAA HPC.

## Tools

| Tool | Description |
|------|-------------|
| `ufs_create_experiment` | Create experiment directory from a template |
| `ufs_validate_experiment` | Check experiment is ready for submission |
| `ufs_submit_experiment` | Submit to Slurm (dry-run by default) |
| `ufs_get_run_status` | Check job status via sacct |
| `ufs_cancel_run` | Cancel a running job |
| `ufs_collect_outputs` | List output files from a completed run |
| `ufs_list_templates` | Show available experiment templates |

## Safety

- Only operates in whitelisted scratch paths (`/scratch*`, `/work*`, `/contrib*`)
- Submission defaults to dry-run mode (shows command without executing)
- Resource limits: max 50 nodes, max 12 hours wall time
- No arbitrary shell commands or file writes outside the run directory
- Full audit trail via `.ufs_experiment.json` metadata

## Usage

```bash
pip install -e .
ufs-runner-mcp
```
