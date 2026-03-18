"""Tests for anomaly check and skill assessment tools."""

import json
import os
import tempfile

import pytest


def _has_xarray() -> bool:
    try:
        import numpy  # noqa: F401
        import xarray  # noqa: F401

        return True
    except ImportError:
        return False


xarray_required = pytest.mark.skipif(not _has_xarray(), reason="xarray not installed")

from nos_workflow_mcp.tools.analysis import nos_anomaly_check, nos_skill_assessment


# ── nos_anomaly_check ────────────────────────────────────────────────────


class TestNosAnomalyCheck:
    @pytest.mark.asyncio
    async def test_unsafe_characters_rejected(self, mock_ctx):
        result = await nos_anomaly_check(mock_ctx, file_path="/tmp/foo;rm -rf /")
        assert "Unsafe characters" in result

    @pytest.mark.asyncio
    async def test_file_not_found(self, mock_ctx):
        result = await nos_anomaly_check(
            mock_ctx, file_path="/tmp/nonexistent_anomaly.nc"
        )
        assert "File not found" in result

    @pytest.mark.asyncio
    @xarray_required
    async def test_variable_not_found(self, mock_ctx):
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            ds = xr.Dataset({"zeta": (["time"], np.array([0.1, 0.2, 0.3]))})
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_anomaly_check(
                mock_ctx, file_path=tmp_path, variable="bogus"
            )
            assert "not found in dataset" in result
            assert "zeta" in result  # lists available variables
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @xarray_required
    async def test_normal_zeta(self, mock_ctx):
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            ds = xr.Dataset(
                {"zeta": (["time", "node"], np.random.uniform(-0.5, 0.5, (10, 50)))}
            )
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_anomaly_check(
                mock_ctx, file_path=tmp_path, variable="zeta"
            )
            assert "NORMAL" in result
            assert "Sigma Deviations" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @xarray_required
    async def test_anomalous_zeta(self, mock_ctx):
        """Zeta values exceeding 5 m should trigger ANOMALY."""
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            values = np.random.uniform(-0.5, 0.5, (10, 50))
            values[0, 0] = 10.0  # well beyond 5 m hard limit
            ds = xr.Dataset({"zeta": (["time", "node"], values)})
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_anomaly_check(
                mock_ctx, file_path=tmp_path, variable="zeta"
            )
            assert "ANOMALY" in result
            assert "Hard Limit" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @xarray_required
    async def test_warning_level(self, mock_ctx):
        """Values between 2-3 sigma should trigger WARNING."""
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            # Baseline mean=0, std=1. A max of 2.5 is 2.5 sigma -> WARNING
            # Keep within hard abs_max of 5 so hard limits don't override
            values = np.zeros((10, 50))
            values[0, 0] = 2.5
            ds = xr.Dataset({"zeta": (["time", "node"], values)})
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_anomaly_check(
                mock_ctx, file_path=tmp_path, variable="zeta"
            )
            assert "WARNING" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @xarray_required
    async def test_user_provided_baseline(self, mock_ctx):
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            ds = xr.Dataset({"zeta": (["time"], np.array([100.0, 101.0, 99.0]))})
            ds.to_netcdf(tmp_path)
            ds.close()
            # With baseline mean=100, std=5 the values are within 1 sigma -> NORMAL
            result = await nos_anomaly_check(
                mock_ctx,
                file_path=tmp_path,
                variable="zeta",
                baseline_mean=100.0,
                baseline_std=5.0,
            )
            assert "NORMAL" in result
            assert "user-provided" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @xarray_required
    async def test_unknown_variable_no_baseline(self, mock_ctx):
        """Variable without climatology and no user baseline -> UNKNOWN."""
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            ds = xr.Dataset({"custom_var": (["time"], np.array([1.0, 2.0, 3.0]))})
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_anomaly_check(
                mock_ctx, file_path=tmp_path, variable="custom_var"
            )
            assert "UNKNOWN" in result
            assert "no baseline available" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @xarray_required
    async def test_temp_anomaly_hard_max(self, mock_ctx):
        """Temperature above 45 should trigger ANOMALY via hard limit."""
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            values = np.array([15.0, 16.0, 50.0])
            ds = xr.Dataset({"temp": (["time"], values)})
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_anomaly_check(
                mock_ctx, file_path=tmp_path, variable="temp"
            )
            assert "ANOMALY" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @xarray_required
    async def test_salt_below_hard_min(self, mock_ctx):
        """Salinity below 0 should trigger ANOMALY via hard limit."""
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            values = np.array([32.0, 30.0, -1.0])
            ds = xr.Dataset({"salt": (["time"], values)})
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_anomaly_check(
                mock_ctx, file_path=tmp_path, variable="salt"
            )
            assert "ANOMALY" in result
        finally:
            os.unlink(tmp_path)


# ── nos_skill_assessment ─────────────────────────────────────────────────


class TestNosSkillAssessment:
    @pytest.mark.asyncio
    async def test_no_observations_provided(self, mock_ctx):
        result = await nos_skill_assessment(
            mock_ctx, model_file="/tmp/model.nc", model_variable="zeta"
        )
        assert "Must provide either obs_file or obs_values" in result

    @pytest.mark.asyncio
    async def test_model_file_not_found(self, mock_ctx):
        result = await nos_skill_assessment(
            mock_ctx,
            model_file="/tmp/nonexistent_model.nc",
            model_variable="zeta",
            obs_values="[1.0, 2.0]",
        )
        assert "Model file not found" in result

    @pytest.mark.asyncio
    async def test_unsafe_model_path(self, mock_ctx):
        result = await nos_skill_assessment(
            mock_ctx,
            model_file="/tmp/foo;bar",
            model_variable="zeta",
            obs_values="[1.0]",
        )
        assert "Unsafe characters" in result

    @pytest.mark.asyncio
    async def test_unsafe_obs_path(self, mock_ctx):
        result = await nos_skill_assessment(
            mock_ctx,
            model_file="/tmp/model.nc",
            model_variable="zeta",
            obs_file="/tmp/obs|bad.nc",
        )
        assert "Unsafe characters" in result

    @pytest.mark.asyncio
    @xarray_required
    async def test_model_variable_not_found(self, mock_ctx):
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            ds = xr.Dataset({"zeta": (["time"], np.array([1.0, 2.0]))})
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_skill_assessment(
                mock_ctx,
                model_file=tmp_path,
                model_variable="bogus",
                obs_values="[1.0, 2.0]",
            )
            assert "not found in model file" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @xarray_required
    async def test_invalid_obs_json(self, mock_ctx):
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            ds = xr.Dataset({"zeta": (["time"], np.array([1.0, 2.0]))})
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_skill_assessment(
                mock_ctx,
                model_file=tmp_path,
                model_variable="zeta",
                obs_values="not-json",
            )
            assert "Error parsing obs_values JSON" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @xarray_required
    async def test_obs_values_not_array(self, mock_ctx):
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            ds = xr.Dataset({"zeta": (["time"], np.array([1.0, 2.0]))})
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_skill_assessment(
                mock_ctx,
                model_file=tmp_path,
                model_variable="zeta",
                obs_values='{"a": 1}',
            )
            assert "must be a JSON array" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @xarray_required
    async def test_perfect_match(self, mock_ctx):
        """Identical model and obs should yield RMSE=0, correlation=1, d=1."""
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            vals = [1.0, 2.0, 3.0, 4.0, 5.0]
            ds = xr.Dataset({"zeta": (["time"], np.array(vals))})
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_skill_assessment(
                mock_ctx,
                model_file=tmp_path,
                model_variable="zeta",
                obs_values=json.dumps(vals),
            )
            assert "Skill Assessment" in result
            assert "RMSE" in result
            # RMSE should be 0
            assert "| RMSE | 0 |" in result
            # Bias should be 0
            assert "| Bias (mean error) | 0 |" in result
            # Correlation should be 1
            assert "| Correlation (r) | 1 |" in result
            # Willmott d should be 1
            assert "| Willmott d | 1 |" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @xarray_required
    async def test_known_bias(self, mock_ctx):
        """Model consistently 2.0 higher than obs -> bias = 2.0."""
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            obs_vals = [1.0, 2.0, 3.0, 4.0, 5.0]
            model_vals = [v + 2.0 for v in obs_vals]
            ds = xr.Dataset({"zeta": (["time"], np.array(model_vals))})
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_skill_assessment(
                mock_ctx,
                model_file=tmp_path,
                model_variable="zeta",
                obs_values=json.dumps(obs_vals),
            )
            assert "| Bias (mean error) | 2 |" in result
            assert "over-predicts" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @xarray_required
    async def test_obs_file_input(self, mock_ctx):
        """Test skill assessment with observations from a NetCDF file."""
        import numpy as np
        import xarray as xr

        model_tmp = tempfile.NamedTemporaryFile(suffix=".nc", delete=False)
        obs_tmp = tempfile.NamedTemporaryFile(suffix=".nc", delete=False)
        try:
            model_vals = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
            obs_vals = np.array([1.1, 1.9, 3.1, 3.9, 5.1])

            xr.Dataset({"zeta": (["time"], model_vals)}).to_netcdf(model_tmp.name)
            xr.Dataset({"obs_wl": (["time"], obs_vals)}).to_netcdf(obs_tmp.name)

            result = await nos_skill_assessment(
                mock_ctx,
                model_file=model_tmp.name,
                model_variable="zeta",
                obs_file=obs_tmp.name,
                obs_variable="obs_wl",
            )
            assert "Skill Assessment" in result
            assert "RMSE" in result
            assert "Paired points" in result
        finally:
            os.unlink(model_tmp.name)
            os.unlink(obs_tmp.name)

    @pytest.mark.asyncio
    @xarray_required
    async def test_obs_file_variable_not_found(self, mock_ctx):
        import numpy as np
        import xarray as xr

        model_tmp = tempfile.NamedTemporaryFile(suffix=".nc", delete=False)
        obs_tmp = tempfile.NamedTemporaryFile(suffix=".nc", delete=False)
        try:
            xr.Dataset({"zeta": (["time"], np.array([1.0, 2.0]))}).to_netcdf(
                model_tmp.name
            )
            xr.Dataset({"wl": (["time"], np.array([1.0, 2.0]))}).to_netcdf(obs_tmp.name)
            result = await nos_skill_assessment(
                mock_ctx,
                model_file=model_tmp.name,
                model_variable="zeta",
                obs_file=obs_tmp.name,
                obs_variable="bogus",
            )
            assert "not found in observations file" in result
        finally:
            os.unlink(model_tmp.name)
            os.unlink(obs_tmp.name)

    @pytest.mark.asyncio
    @xarray_required
    async def test_too_few_points(self, mock_ctx):
        """Fewer than 2 valid points should produce an error."""
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            ds = xr.Dataset({"zeta": (["time"], np.array([1.0]))})
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_skill_assessment(
                mock_ctx,
                model_file=tmp_path,
                model_variable="zeta",
                obs_values="[1.0]",
            )
            assert "Fewer than 2" in result
        finally:
            os.unlink(tmp_path)

    @pytest.mark.asyncio
    @xarray_required
    async def test_mismatched_lengths_uses_shorter(self, mock_ctx):
        """When model and obs differ in length, use the shorter series."""
        import numpy as np
        import xarray as xr

        with tempfile.NamedTemporaryFile(suffix=".nc", delete=False) as f:
            tmp_path = f.name
        try:
            ds = xr.Dataset({"zeta": (["time"], np.array([1.0, 2.0, 3.0, 4.0, 5.0]))})
            ds.to_netcdf(tmp_path)
            ds.close()
            result = await nos_skill_assessment(
                mock_ctx,
                model_file=tmp_path,
                model_variable="zeta",
                obs_values="[1.0, 2.0, 3.0]",
            )
            assert "Skill Assessment" in result
            assert "3 (of 3 aligned)" in result or "Paired points" in result
        finally:
            os.unlink(tmp_path)
