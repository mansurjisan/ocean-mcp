"""Tests for MCP tool functions using mocked executor."""

import pytest

from hpc_system_mcp.tools.quota import hpc_disk_quota, hpc_df  # noqa: F401
from hpc_system_mcp.tools.allocation import (
    hpc_fairshare,
    hpc_account_info,
    hpc_job_priority,
)
from hpc_system_mcp.tools.modules import (
    hpc_module_list,
    hpc_module_avail,
    hpc_module_info,
)
from hpc_system_mcp.tools.system import (
    hpc_system_info,
    hpc_user_groups,
    hpc_recent_jobs,
)


class TestQuotaTools:
    @pytest.mark.asyncio
    async def test_disk_quota(self, mock_ctx, mock_executor):
        mock_executor.run.return_value = (
            "Disk quotas for user testuser:\n  /home: 5G/10G"
        )
        result = await hpc_disk_quota(mock_ctx, filesystem="/home")
        assert "Home Quota" in result
        assert "5G/10G" in result

    @pytest.mark.asyncio
    async def test_df(self, mock_ctx, mock_executor):
        mock_executor.run.return_value = "Filesystem  Size  Used  Avail  Use%  Mounted on\n/dev/sda1  100G  50G  50G  50%  /"
        result = await hpc_df(mock_ctx)
        assert "Disk Space" in result
        assert "100G" in result

    @pytest.mark.asyncio
    async def test_df_unsafe_path(self, mock_ctx):
        result = await hpc_df(mock_ctx, filesystem="/tmp; rm -rf /")
        assert "Error" in result


class TestAllocationTools:
    @pytest.mark.asyncio
    async def test_fairshare(self, mock_ctx, mock_executor):
        mock_executor.run.return_value = (
            "Account       User  RawShares  NormShares  RawUsage  EffectvUsage  FairShare\n"
            "coastal-act   user1  100        0.5         1000      0.3           0.7"
        )
        result = await hpc_fairshare(mock_ctx, account="coastal-act")
        assert "FairShare" in result
        assert "coastal-act" in result
        assert "> 0.5" in result  # Explanation text

    @pytest.mark.asyncio
    async def test_account_info(self, mock_ctx, mock_executor):
        mock_executor.run.return_value = (
            "coastal-act|u1-compute|batch|10|20|08:00:00|cpu=1000"
        )
        result = await hpc_account_info(mock_ctx)
        assert "Slurm Accounts" in result
        assert "coastal-act" in result

    @pytest.mark.asyncio
    async def test_job_priority_invalid_id(self, mock_ctx):
        result = await hpc_job_priority(mock_ctx, job_id="abc")
        assert "Error" in result
        assert "Invalid" in result

    @pytest.mark.asyncio
    async def test_job_priority_valid(self, mock_ctx, mock_executor):
        mock_executor.run.return_value = (
            "JOBID  PRIORITY  AGE  FAIRSHARE\n12345  1000  100  500"
        )
        result = await hpc_job_priority(mock_ctx, job_id="12345")
        assert "Job Priority" in result
        assert "12345" in result


class TestModuleTools:
    @pytest.mark.asyncio
    async def test_module_list(self, mock_ctx, mock_executor):
        mock_executor.run_shell.return_value = (
            "Currently Loaded Modules:\n"
            "  1) intel/2023.2.0  2) impi/2023.2.0  3) netcdf-c/4.9.2"
        )
        result = await hpc_module_list(mock_ctx)
        assert "Loaded Modules" in result
        assert "intel" in result

    @pytest.mark.asyncio
    async def test_module_list_empty(self, mock_ctx, mock_executor):
        mock_executor.run_shell.return_value = "No modules loaded"
        result = await hpc_module_list(mock_ctx)
        assert "No modules" in result

    @pytest.mark.asyncio
    async def test_module_avail_search(self, mock_ctx, mock_executor):
        mock_executor.run_shell.return_value = (
            "netcdf-c:\n  netcdf-c/4.9.2\n  netcdf-c/4.9.0"
        )
        result = await hpc_module_avail(mock_ctx, search="netcdf")
        assert "Module Search" in result
        assert "netcdf" in result

    @pytest.mark.asyncio
    async def test_module_avail_unsafe(self, mock_ctx):
        result = await hpc_module_avail(mock_ctx, search="test; rm -rf /")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_module_info(self, mock_ctx, mock_executor):
        mock_executor.run_shell.return_value = (
            "/apps/modules/netcdf-c/4.9.2.lua:\n"
            'setenv("NETCDF_C_ROOT", "/apps/spack/netcdf-c-4.9.2")'
        )
        result = await hpc_module_info(mock_ctx, module_name="netcdf-c/4.9.2")
        assert "Module: netcdf-c" in result
        assert "NETCDF_C_ROOT" in result


class TestSystemTools:
    @pytest.mark.asyncio
    async def test_system_info(self, mock_ctx, mock_executor):
        mock_executor.run.return_value = (
            "PARTITION  AVAIL  NODES  CPUS  MEMORY  TIMELIMIT  STATE\n"
            "u1-compute  up    500    192   384000  8:00:00    idle"
        )
        result = await hpc_system_info(mock_ctx)
        assert "System Info" in result
        assert "u1-compute" in result

    @pytest.mark.asyncio
    async def test_user_groups(self, mock_ctx, mock_executor):
        mock_executor.run.side_effect = [
            "uid=12345(testuser) gid=1000(coastal) groups=1000(coastal),2000(noaa)",
            "testuser : coastal noaa",
        ]
        result = await hpc_user_groups(mock_ctx)
        assert "User:" in result
        assert "coastal" in result

    @pytest.mark.asyncio
    async def test_user_groups_unsafe(self, mock_ctx):
        result = await hpc_user_groups(mock_ctx, user="test; whoami")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_recent_jobs(self, mock_ctx, mock_executor):
        mock_executor.run.return_value = (
            "JobID  JobName  Partition  Account  AllocCPUS  State  Elapsed\n"
            "12345  test.sh  u1-compute coastal-act 192  COMPLETED  01:30:00"
        )
        result = await hpc_recent_jobs(mock_ctx, days=7)
        assert "Recent Jobs" in result
        assert "7 days" in result

    @pytest.mark.asyncio
    async def test_recent_jobs_unsafe_account(self, mock_ctx):
        result = await hpc_recent_jobs(mock_ctx, account="test; whoami")
        assert "Error" in result
