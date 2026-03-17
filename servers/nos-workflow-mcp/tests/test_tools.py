"""Tests for MCP tool functions."""

import pytest

from nos_workflow_mcp.tools.config import (
    nos_list_systems,
    nos_get_config,
    nos_compare_configs,
    nos_get_ecflow_suite,
    nos_get_ensemble_config,
)
from nos_workflow_mcp.tools.diagnostics import nos_diagnose_failure


class TestConfigTools:
    @pytest.mark.asyncio
    async def test_list_systems(self, mock_ctx):
        result = await nos_list_systems(mock_ctx)
        assert "secofs" in result
        assert "stofs_3d_atl" in result
        assert "SCHISM" in result

    @pytest.mark.asyncio
    async def test_get_config(self, mock_ctx):
        result = await nos_get_config(mock_ctx, system_name="secofs")
        assert "secofs" in result
        assert "Configuration" in result

    @pytest.mark.asyncio
    async def test_get_config_section(self, mock_ctx):
        result = await nos_get_config(
            mock_ctx, system_name="secofs", section="forcing.atmospheric"
        )
        assert "GFS" in result

    @pytest.mark.asyncio
    async def test_compare_configs(self, mock_ctx):
        result = await nos_compare_configs(
            mock_ctx, system_a="secofs", system_b="stofs_3d_atl"
        )
        assert "Comparison" in result
        assert "secofs" in result
        assert "stofs_3d_atl" in result

    @pytest.mark.asyncio
    async def test_ecflow_suite(self, mock_ctx):
        result = await nos_get_ecflow_suite(mock_ctx, system_name="stofs_3d_atl")
        assert "stofs_3d_atl" in result
        assert "prep" in result

    @pytest.mark.asyncio
    async def test_ensemble_config(self, mock_ctx):
        result = await nos_get_ensemble_config(mock_ctx, system_name="secofs")
        assert "Ensemble" in result
        assert "gefs" in result.lower() or "GEFS" in result

    @pytest.mark.asyncio
    async def test_ensemble_not_found(self, mock_ctx):
        result = await nos_get_ensemble_config(mock_ctx, system_name="cbofs")
        assert "No ensemble" in result


class TestDiagnosticsTools:
    @pytest.mark.asyncio
    async def test_diagnose_h_c(self, mock_ctx):
        result = await nos_diagnose_failure(
            mock_ctx,
            log_content="0: ABORT:  h_c needs to be larger:   30.0",
        )
        assert "SCHISM vertical coordinate" in result
        assert "vgrid.in" in result

    @pytest.mark.asyncio
    async def test_diagnose_cfl(self, mock_ctx):
        result = await nos_diagnose_failure(
            mock_ctx,
            log_content="CFL violation at timestep 500",
        )
        assert "CFL" in result
