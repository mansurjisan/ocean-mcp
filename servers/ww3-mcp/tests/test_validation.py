"""Tests for WW3 MCP model validation — enums, registry, and constants.

These tests verify that the data models and grid registry are correctly
defined without any HTTP calls.
"""

from __future__ import annotations

from ww3_mcp.models import (
    GRIB_VAR_FILTER,
    VARIABLE_INFO,
    WAVE_GRIDS,
    WaveGrid,
    WaveVariable,
)


# ============================================================================
# WaveGrid enum
# ============================================================================


class TestWaveGridEnum:
    """Tests for the WaveGrid enumeration."""

    def test_all_grids_have_registry_entries(self):
        """Every WaveGrid enum value should have an entry in WAVE_GRIDS."""
        for grid in WaveGrid:
            assert grid.value in WAVE_GRIDS, (
                f"Grid '{grid.value}' missing from WAVE_GRIDS registry"
            )

    def test_grid_count(self):
        """WaveGrid should have exactly 6 grids."""
        assert len(WaveGrid) == 6

    def test_grid_values_are_strings(self):
        """WaveGrid values should be dot-separated strings."""
        for grid in WaveGrid:
            assert isinstance(grid.value, str)
            assert "." in grid.value or "km" in grid.value


# ============================================================================
# WaveVariable enum
# ============================================================================


class TestWaveVariableEnum:
    """Tests for the WaveVariable enumeration."""

    def test_all_variables_have_filter_keys(self):
        """Every WaveVariable should have a GRIB filter parameter mapping."""
        for var in WaveVariable:
            assert var.value in GRIB_VAR_FILTER, (
                f"Variable '{var.value}' missing from GRIB_VAR_FILTER"
            )

    def test_all_variables_have_info(self):
        """Every WaveVariable should have a VARIABLE_INFO entry."""
        for var in WaveVariable:
            assert var.value in VARIABLE_INFO, (
                f"Variable '{var.value}' missing from VARIABLE_INFO"
            )

    def test_variable_info_has_name_and_units(self):
        """Each VARIABLE_INFO entry should have 'name' and 'units' keys."""
        for var_id, info in VARIABLE_INFO.items():
            assert "name" in info, f"Variable '{var_id}' missing 'name'"
            assert "units" in info, f"Variable '{var_id}' missing 'units'"

    def test_wave_height_variable_exists(self):
        """HTSGW (significant wave height) should be defined."""
        assert WaveVariable.HTSGW.value == "HTSGW"


# ============================================================================
# WAVE_GRIDS registry
# ============================================================================


class TestWaveGridsRegistry:
    """Tests for the WAVE_GRIDS configuration dictionary."""

    def test_all_grids_have_required_keys(self):
        """Each grid entry should contain all required metadata keys."""
        required = {
            "name",
            "short_name",
            "resolution",
            "domain_desc",
            "domain",
            "cycles",
            "forecast_hours",
            "file_template",
            "dir_template",
        }
        for grid_id, info in WAVE_GRIDS.items():
            missing = required - set(info.keys())
            assert not missing, f"Grid '{grid_id}' missing keys: {missing}"

    def test_all_grids_have_domain_bounds(self):
        """Each grid domain should have lat_min, lat_max, lon_min, lon_max."""
        for grid_id, info in WAVE_GRIDS.items():
            domain = info["domain"]
            for key in ("lat_min", "lat_max", "lon_min", "lon_max"):
                assert key in domain, f"Grid '{grid_id}' domain missing '{key}'"
                assert isinstance(domain[key], (int, float))

    def test_global_grid_covers_full_latitude_range(self):
        """Global grids should cover -90 to 90 latitude."""
        for grid_id in ("global.0p16", "global.0p25"):
            domain = WAVE_GRIDS[grid_id]["domain"]
            assert domain["lat_min"] == -90.0
            assert domain["lat_max"] == 90.0

    def test_all_grids_have_four_cycles(self):
        """All GFS-Wave grids should have 4 daily cycles."""
        for grid_id, info in WAVE_GRIDS.items():
            assert len(info["cycles"]) == 4, f"Grid '{grid_id}' should have 4 cycles"

    def test_forecast_hours_are_positive(self):
        """All grids should have positive forecast hours."""
        for grid_id, info in WAVE_GRIDS.items():
            assert info["forecast_hours"] > 0

    def test_file_template_contains_placeholders(self):
        """File templates should contain {cycle} and {fhour} placeholders."""
        for grid_id, info in WAVE_GRIDS.items():
            tpl = info["file_template"]
            assert "{cycle}" in tpl, f"Grid '{grid_id}' template missing {{cycle}}"
            assert "{fhour" in tpl, f"Grid '{grid_id}' template missing {{fhour}}"

    def test_dir_template_contains_date(self):
        """Dir templates should contain {date} placeholder."""
        for grid_id, info in WAVE_GRIDS.items():
            tpl = info["dir_template"]
            assert "{date}" in tpl, f"Grid '{grid_id}' dir template missing {{date}}"


# ============================================================================
# GRIB_VAR_FILTER
# ============================================================================


class TestGribVarFilter:
    """Tests for the GRIB variable filter parameter mapping."""

    def test_filter_keys_start_with_var(self):
        """All GRIB filter parameter names should start with 'var_'."""
        for var, filter_key in GRIB_VAR_FILTER.items():
            assert filter_key.startswith("var_"), (
                f"Filter key for '{var}' should start with 'var_'"
            )

    def test_filter_keys_match_variable_names(self):
        """Filter parameter should be 'var_' + the variable name."""
        for var, filter_key in GRIB_VAR_FILTER.items():
            assert filter_key == f"var_{var}"
