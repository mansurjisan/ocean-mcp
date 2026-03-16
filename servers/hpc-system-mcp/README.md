# hpc-system-mcp

MCP server for NOAA RDHPCS HPC system management. Provides tools for checking disk quotas, allocation usage, FairShare status, loaded modules, and storage information across NOAA HPC systems (Ursa, Hercules, Hera, Orion).

## Tools

| Tool | Description |
|------|-------------|
| `hpc_disk_quota` | Check home and scratch disk quotas |
| `hpc_storage_usage` | Summarize directory sizes |
| `hpc_allocation_usage` | Show core-hour allocation and usage via sreport |
| `hpc_fairshare` | Show FairShare status for accounts |
| `hpc_account_info` | Show Slurm account associations and limits |
| `hpc_module_list` | List currently loaded modules |
| `hpc_module_avail` | Search available modules |
| `hpc_system_info` | Show node/partition info via sinfo |

## Installation

```bash
pip install -e .
```
