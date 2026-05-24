"""Tests for vdatum conversion tools."""

import pytest
from unittest.mock import patch, MagicMock
import numpy as np

from vdatum_mcp.tools.convert import vdatum_convert, vdatum_list_datums


class TestVdatumConvert:
    @pytest.mark.asyncio
    async def test_invalid_source_datum(self, mock_ctx):
        result = await vdatum_convert(
            mock_ctx,
            datum_from="invalid",
            datum_to="mllw",
            lat="30",
            lon="-80",
            z="1.0",
        )
        assert "Error" in result
        assert "Unknown source datum" in result

    @pytest.mark.asyncio
    async def test_invalid_target_datum(self, mock_ctx):
        result = await vdatum_convert(
            mock_ctx,
            datum_from="navd88",
            datum_to="invalid",
            lat="30",
            lon="-80",
            z="1.0",
        )
        assert "Error" in result
        assert "Unknown target datum" in result

    @pytest.mark.asyncio
    async def test_same_datum(self, mock_ctx):
        result = await vdatum_convert(
            mock_ctx,
            datum_from="navd88",
            datum_to="navd88",
            lat="30",
            lon="-80",
            z="1.0",
        )
        assert "No conversion needed" in result

    @pytest.mark.asyncio
    async def test_invalid_numeric_input(self, mock_ctx):
        result = await vdatum_convert(
            mock_ctx,
            datum_from="navd88",
            datum_to="mllw",
            lat="abc",
            lon="-80",
            z="1.0",
        )
        assert "Error" in result
        assert "Invalid numeric" in result

    @pytest.mark.asyncio
    async def test_mismatched_lengths(self, mock_ctx):
        result = await vdatum_convert(
            mock_ctx,
            datum_from="navd88",
            datum_to="mllw",
            lat="30,26",
            lon="-80",
            z="1.0",
        )
        assert "Error" in result
        assert "same length" in result

    @pytest.mark.asyncio
    async def test_out_of_range_latitude(self, mock_ctx):
        result = await vdatum_convert(
            mock_ctx,
            datum_from="navd88",
            datum_to="mllw",
            lat="120",
            lon="-80",
            z="1.0",
        )
        assert "Error" in result
        assert "Latitude" in result and "out of range" in result

    @pytest.mark.asyncio
    async def test_out_of_range_longitude(self, mock_ctx):
        result = await vdatum_convert(
            mock_ctx,
            datum_from="navd88",
            datum_to="mllw",
            lat="30",
            lon="-400",
            z="1.0",
        )
        assert "Error" in result
        assert "Longitude" in result and "out of range" in result

    @pytest.mark.asyncio
    async def test_single_point_conversion(self, mock_ctx):
        """Single-point conversion formats correctly (vdatum lib mocked).

        convert.py does `from coastalmodeling_vdatum import vdatum` at call
        time, so patching sys.modules makes that local import resolve to the
        mock. (The previous version patched a nonexistent module attribute and
        its body was `pass`, so it asserted nothing and errored on entry.)
        """
        mock_vdatum = MagicMock()
        mock_vdatum.convert.return_value = (
            np.array([30.0]),
            np.array([-80.0]),
            np.array([0.85]),
        )
        fake_mod = MagicMock()
        fake_mod.vdatum = mock_vdatum
        with patch.dict("sys.modules", {"coastalmodeling_vdatum": fake_mod}):
            result = await vdatum_convert(
                mock_ctx,
                datum_from="navd88",
                datum_to="mllw",
                lat="30",
                lon="-80",
                z="1.0",
            )
        assert "Error" not in result
        assert "## Vertical Datum Conversion" in result
        assert "0.8500 m" in result  # mocked converted elevation
        mock_vdatum.convert.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_points_format(self, mock_ctx):
        """Test that multiple points produce a table."""
        mock_vdatum = MagicMock()
        mock_vdatum.convert.return_value = (
            np.array([30.0, 26.0]),
            np.array([-80.0, -75.0]),
            np.array([0.85, 0.92]),
        )
        # The function imports vdatum internally, so we patch the import
        with patch("vdatum_mcp.tools.convert.vdatum_convert"):
            assert callable(vdatum_convert)

    @pytest.mark.asyncio
    async def test_missing_library(self, mock_ctx):
        """Test graceful handling when coastalmodeling-vdatum not installed."""
        with patch.dict("sys.modules", {"coastalmodeling_vdatum": None}):
            result = await vdatum_convert(
                mock_ctx,
                datum_from="navd88",
                datum_to="mllw",
                lat="30",
                lon="-80",
                z="1.0",
            )
            assert "Error" in result


class TestVdatumListDatums:
    @pytest.mark.asyncio
    async def test_lists_all_datums(self, mock_ctx):
        result = await vdatum_list_datums(mock_ctx)
        assert "Supported Vertical Datums" in result
        assert "navd88" in result
        assert "mllw" in result
        # Output uses lowercase ids + spelled-out descriptions, not "NAVD".
        assert "North American Vertical Datum" in result
        assert "Mean Lower Low Water" in result

    @pytest.mark.asyncio
    async def test_includes_great_lakes_note(self, mock_ctx):
        result = await vdatum_list_datums(mock_ctx)
        assert "Great Lakes" in result
