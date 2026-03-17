"""Tests for ConfigReader core logic."""

import pytest

from nos_workflow_mcp.config_reader import ConfigError


class TestListSystems:
    def test_lists_all_systems(self, reader):
        systems = reader.list_systems()
        names = [s["name"] for s in systems]
        assert "secofs" in names
        assert "stofs_3d_atl" in names
        assert "cbofs" in names

    def test_includes_metadata(self, reader):
        systems = reader.list_systems()
        secofs = next(s for s in systems if s["name"] == "secofs")
        assert secofs["model"] == "SCHISM"
        assert secofs["framework"] == "comf"


class TestGetConfig:
    def test_reads_secofs(self, reader):
        config = reader.get_config("secofs")
        assert config["system"]["name"] == "secofs"
        assert config["system"]["framework"] == "comf"

    def test_reads_stofs_3d_atl(self, reader):
        config = reader.get_config("stofs_3d_atl")
        assert config["system"]["name"] == "stofs_3d_atl"
        assert config["system"]["framework"] == "stofs"

    def test_reads_grid_section(self, reader):
        config = reader.get_config("secofs")
        assert "grid" in config
        assert config["grid"]["n_nodes"] == 1684786

    def test_reads_forcing_section(self, reader):
        config = reader.get_config("secofs")
        assert config["forcing"]["atmospheric"]["primary"] == "GFS"

    def test_reads_physics(self, reader):
        config = reader.get_config("secofs")
        assert config["model"]["physics"]["dt"] == 120.0

    def test_nonexistent_system_raises(self, reader):
        with pytest.raises(ConfigError, match="not found"):
            reader.get_config("nonexistent_system")


class TestGetConfigSection:
    def test_dot_notation(self, reader):
        result = reader.get_config_section("secofs", "model.physics.dt")
        assert result == 120.0

    def test_forcing_atmospheric(self, reader):
        result = reader.get_config_section("secofs", "forcing.atmospheric")
        assert result["primary"] == "GFS"
        assert result["secondary"] == "HRRR"

    def test_grid_domain(self, reader):
        result = reader.get_config_section("secofs", "grid.domain")
        assert result["lon_min"] == -88.0

    def test_missing_section_returns_none(self, reader):
        result = reader.get_config_section("secofs", "nonexistent.section")
        assert result is None


class TestCompareConfigs:
    def test_finds_differences(self, reader):
        result = reader.compare_configs("secofs", "stofs_3d_atl")
        assert "grid" in result["differences"]

    def test_grid_sizes_differ(self, reader):
        result = reader.compare_configs("secofs", "stofs_3d_atl", ["grid"])
        secofs_grid = result["differences"]["grid"]["secofs"]
        stofs_grid = result["differences"]["grid"]["stofs_3d_atl"]
        assert secofs_grid["n_nodes"] != stofs_grid["n_nodes"]


class TestEcflowSuite:
    def test_reads_full_suite(self, reader):
        content = reader.get_ecflow_suite()
        assert "suite nosofs" in content
        assert "stofs_3d_atl" in content

    def test_reads_specific_system(self, reader):
        content = reader.get_ecflow_suite("stofs_3d_atl")
        assert "stofs_3d_atl" in content
        assert "prep" in content
        assert "nowcast" in content


class TestEnsembleConfig:
    def test_secofs_has_ensemble(self, reader):
        ensemble = reader.get_ensemble_config("secofs")
        assert ensemble is not None
        assert ensemble["n_members"] == 6
        assert ensemble["method"] == "gefs"

    def test_cbofs_no_ensemble(self, reader):
        ensemble = reader.get_ensemble_config("cbofs")
        assert ensemble is None


class TestDiagnoseLog:
    def test_h_c_error(self, reader):
        log = "0: ABORT:  h_c needs to be larger:   30.0000000000000"
        result = reader.diagnose_log(log)
        assert result["error_type"] == "SCHISM vertical coordinate"
        assert "30.0" in result["error_message"]
        assert "vgrid.in" in result["suggestion"]

    def test_cfl_error(self, reader):
        log = "CFL violation detected at step 1234"
        result = reader.diagnose_log(log)
        assert result["error_type"] == "CFL violation"

    def test_mpi_error(self, reader):
        log = "MPI_ABORT was invoked on rank 0"
        result = reader.diagnose_log(log)
        assert result["error_type"] == "MPI failure"

    def test_oom_error(self, reader):
        log = "slurmstepd: error: Detected 1 oom-kill event(s)"
        result = reader.diagnose_log(log)
        assert result["error_type"] == "Out of memory"

    def test_timeout_error(self, reader):
        log = "CANCELLED AT 2026-03-16T20:00:00 DUE TO TIME LIMIT"
        result = reader.diagnose_log(log)
        assert result["error_type"] == "Wall time exceeded"

    def test_missing_file(self, reader):
        log = "FileNotFoundError: No such file or directory: '/com/gfs/gfs.20260316/gfs.t12z.pgrb2.0p25.f003'"
        result = reader.diagnose_log(log)
        assert result["error_type"] == "Missing file"

    def test_unknown_error(self, reader):
        log = "Something weird happened"
        result = reader.diagnose_log(log)
        assert result["error_type"] == "unknown"
