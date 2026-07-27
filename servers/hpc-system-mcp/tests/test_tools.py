"""Tests for MCP tool functions using mocked executor."""

import os

import pytest

from hpc_system_mcp.tools.quota import (  # noqa: F401
    hpc_disk_quota,
    hpc_df,
    hpc_storage_usage,
)
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
    hpc_partition_limits,
)
from hpc_system_mcp.executor import ExecutorError
from hpc_system_mcp.tools.pbs import (
    hpc_pbs_jobs,
    hpc_pbs_job_detail,
    hpc_pbs_nodes,
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

    @pytest.mark.asyncio
    async def test_storage_usage_sorted_with_total(
        self, mock_ctx, mock_executor, monkeypatch
    ):
        """Details are sorted largest-first and the grand total (du's last
        line) is reported correctly."""
        monkeypatch.setattr(os.path, "isdir", lambda path: True)
        mock_executor.run.return_value = (
            "504K\t/scratch5/user/a\n"
            "2.0M\t/scratch5/user/b\n"
            "104K\t/scratch5/user/c\n"
            "2.6M\t/scratch5/user"
        )
        result = await hpc_storage_usage(mock_ctx, directory="/scratch5/user")
        assert "**Total**: 2.6M" in result
        # Largest subdirectory (2.0M) must be listed before the smaller ones.
        assert result.index("2.0M") < result.index("504K") < result.index("104K")
        # The total (2.6M) must appear only in the Total line, not duplicated
        # as one of the sorted detail rows.
        assert result.count("2.6M") == 1

    @pytest.mark.asyncio
    async def test_storage_usage_unsafe_path(self, mock_ctx):
        result = await hpc_storage_usage(mock_ctx, directory="/tmp; rm -rf /")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_storage_usage_missing_directory(self, mock_ctx, monkeypatch):
        monkeypatch.setattr(os.path, "isdir", lambda path: False)
        result = await hpc_storage_usage(mock_ctx, directory="/no/such/dir")
        assert "does not exist" in result

    @pytest.mark.asyncio
    async def test_storage_usage_du_command_has_no_conflicting_flags(
        self, mock_ctx, mock_executor, monkeypatch
    ):
        """--summarize and --max-depth are mutually exclusive in GNU du; the
        primary command must not combine them. Previously this always
        failed and silently fell back, paying for two full directory
        traversals on every call."""
        monkeypatch.setattr(os.path, "isdir", lambda path: True)
        mock_executor.run.return_value = "1.0G\t/scratch5/user"
        await hpc_storage_usage(mock_ctx, directory="/scratch5/user")
        assert mock_executor.run.call_count == 1
        cmd = mock_executor.run.call_args.args[0]
        assert "--summarize" not in cmd
        assert "du" in cmd[0]

    @pytest.mark.asyncio
    async def test_storage_usage_truncated_output_does_not_corrupt_total(
        self, mock_ctx, mock_executor, monkeypatch
    ):
        """A truncated `du` output must never render '**Total**: ...' — the
        tool should report the total as unknown rather than mis-parsing the
        truncation marker as a size."""
        monkeypatch.setattr(os.path, "isdir", lambda path: True)
        mock_executor.run.return_value = (
            "504K\t/scratch5/user/a\n2.0M\t/scratch5/user/b\n... (truncated)"
        )
        result = await hpc_storage_usage(mock_ctx, directory="/scratch5/user")
        assert "**Total**: unknown" in result
        assert "**Total**: ..." not in result


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
    async def test_account_info_unsafe_user(self, mock_ctx):
        result = await hpc_account_info(mock_ctx, user="test; whoami")
        assert "Error" in result

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
        mock_executor.run_module.return_value = (
            "Currently Loaded Modules:\n"
            "  1) intel/2023.2.0  2) impi/2023.2.0  3) netcdf-c/4.9.2"
        )
        result = await hpc_module_list(mock_ctx)
        assert "Loaded Modules" in result
        assert "intel" in result

    @pytest.mark.asyncio
    async def test_module_list_empty(self, mock_ctx, mock_executor):
        mock_executor.run_module.return_value = "No modules loaded"
        result = await hpc_module_list(mock_ctx)
        assert "No modules" in result

    @pytest.mark.asyncio
    async def test_module_avail_search(self, mock_ctx, mock_executor):
        mock_executor.run_module.return_value = (
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
        mock_executor.run_module.return_value = (
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
    async def test_partition_limits_sbatch_limits(self, mock_ctx, mock_executor):
        """Primary path: sbatch-limits output is rendered."""
        mock_executor.run.return_value = (
            "Partition  MaxNodes  MaxWall\ndebug  10  01:00:00"
        )
        result = await hpc_partition_limits(mock_ctx)
        assert "Partition & QOS Limits" in result
        assert "debug" in result

    @pytest.mark.asyncio
    async def test_partition_limits_falls_back_to_sinfo(self, mock_ctx, mock_executor):
        """When sbatch-limits is absent, fall back to sinfo (not an error)."""
        mock_executor.run.side_effect = [
            ExecutorError("sbatch-limits: not found"),
            "PARTITION  TIMELIMIT  NODES\nu1-compute  8:00:00  500",
        ]
        result = await hpc_partition_limits(mock_ctx)
        assert "via sinfo" in result
        assert "u1-compute" in result

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


class TestPBSTools:
    @pytest.mark.asyncio
    async def test_pbs_jobs(self, mock_ctx, mock_executor):
        mock_executor.run.return_value = (
            "                                                            Req'd  Req'd   Elap\n"
            "Job ID          Username Queue    Jobname    SessID NDS TSK Memory Time  S Time\n"
            "--------------- -------- -------- ---------- ------ --- --- ------ ----- - -----\n"
            "12345.svc       testuser workq    stofs_run  10234    4  96  240gb 06:00 R 02:15"
        )
        result = await hpc_pbs_jobs(mock_ctx)
        assert "PBS Jobs" in result
        assert "12345.svc" in result
        assert "stofs_run" in result

    @pytest.mark.asyncio
    async def test_pbs_job_detail_invalid_id(self, mock_ctx):
        result = await hpc_pbs_job_detail(mock_ctx, job_id="abc; rm -rf /")
        assert "Error" in result
        assert "Invalid" in result

    @pytest.mark.asyncio
    async def test_pbs_job_detail_valid(self, mock_ctx, mock_executor):
        mock_executor.run.return_value = (
            "Job Id: 12345.svc\n"
            "    Job_Name = stofs_run\n"
            "    job_state = R\n"
            "    queue = workq\n"
            "    Resource_List.ncpus = 96"
        )
        result = await hpc_pbs_job_detail(mock_ctx, job_id="12345")
        assert "PBS Job Detail" in result
        assert "12345" in result

    @pytest.mark.asyncio
    async def test_pbs_job_detail_with_server_suffix(self, mock_ctx, mock_executor):
        mock_executor.run.return_value = "Job Id: 12345.svc\n    job_state = R"
        result = await hpc_pbs_job_detail(mock_ctx, job_id="12345.svc")
        assert "PBS Job Detail" in result
        assert "12345.svc" in result

    @pytest.mark.asyncio
    async def test_pbs_nodes(self, mock_ctx, mock_executor):
        mock_executor.run.return_value = (
            "                                                        mem   ncpus   nmics   ngpus\n"
            "vnode           state           njobs   run   susp      f/t     f/t     f/t     f/t\n"
            "--------------- --------------- ------ ----- ------ -------- ------- ------- -------\n"
            "t001            free                 0     0      0  512/512 128/128     0/0     0/0"
        )
        result = await hpc_pbs_nodes(mock_ctx)
        assert "PBS Node Status" in result
        assert "t001" in result
