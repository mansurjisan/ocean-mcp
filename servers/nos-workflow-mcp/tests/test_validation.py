"""Tests for validation and availability tools."""

import os
import tempfile
from unittest.mock import patch

import pytest

from nos_workflow_mcp.tools.validation import nos_validate_output
from nos_workflow_mcp.tools.availability import nos_check_forcing


def _has_xarray() -> bool:
    try:
        import numpy  # noqa: F401
        import xarray  # noqa: F401

        return True
    except ImportError:
        return False


class TestNosValidateOutput:
    @pytest.mark.asyncio
    async def test_unsafe_characters_rejected(self, mock_ctx):
        result = await nos_validate_output(mock_ctx, file_path="/tmp/foo;rm -rf /")
        assert "Unsafe characters" in result

    @pytest.mark.asyncio
    async def test_file_not_found(self, mock_ctx):
        result = await nos_validate_output(
            mock_ctx, file_path="/tmp/nonexistent_file.nc"
        )
        assert "File not found" in result

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _has_xarray(), reason="xarray not installed")
    async def test_valid_netcdf_passes(self, mock_ctx):
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            ds = xr.Dataset(
                {
                    "zeta": (["time", "node"], np.random.uniform(-1, 1, (10, 100))),
                    "temp": (["time", "node"], np.random.uniform(10, 25, (10, 100))),
                }
            )
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_validate_output(mock_ctx, file_path=tmp_path)
            assert "PASS" in result
            assert "zeta" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @pytest.mark.skipif(not _has_xarray(), reason="xarray not installed")
    async def test_extreme_zeta_triggers_error(self, mock_ctx):
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            values = np.random.uniform(-1, 1, (10, 100))
            values[5, 50] = 999.0
            ds = xr.Dataset({"zeta": (["time", "node"], values)})
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_validate_output(mock_ctx, file_path=tmp_path)
            assert "FAIL" in result
            assert "extreme values" in result
        finally:
            os.unlink(tmp_path)


class TestNosCheckForcing:
    @pytest.mark.asyncio
    async def test_invalid_system_returns_error(self, mock_ctx):
        result = await nos_check_forcing(mock_ctx, system_name="nonexistent_system")
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_secofs_checks_gfs(self, mock_ctx):
        result = await nos_check_forcing(
            mock_ctx, system_name="secofs", date="20260316", cycle="12"
        )
        assert "Forcing Availability" in result
        assert "GFS" in result

    @pytest.mark.asyncio
    async def test_secofs_checks_all_sources(self, mock_ctx):
        result = await nos_check_forcing(
            mock_ctx, system_name="secofs", date="20260316", cycle="12"
        )
        assert "HRRR" in result
        assert "RTOFS" in result
        assert "NWM" in result

    @pytest.mark.asyncio
    async def test_missing_data_shows_paths(self, mock_ctx):
        result = await nos_check_forcing(
            mock_ctx, system_name="secofs", date="20260316", cycle="12"
        )
        assert "SOME MISSING" in result
