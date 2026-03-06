"""Embedded domain knowledge for SCHISM model configuration."""

from enum import Enum

SCHISM_DOCS_BASE = "https://schism-dev.github.io/schism"


class NamelistSection(str, Enum):
    """Sections in param.nml."""

    CORE = "CORE"
    OPT = "OPT"
    SCHOUT = "SCHOUT"


# Tidal constituent reference (shared with ADCIRC)
TIDAL_CONSTITUENTS: dict[str, dict] = {
    "M2": {"period_hours": 12.4206, "description": "Principal lunar semidiurnal"},
    "S2": {"period_hours": 12.0000, "description": "Principal solar semidiurnal"},
    "N2": {"period_hours": 12.6583, "description": "Larger lunar elliptic semidiurnal"},
    "K2": {"period_hours": 11.9672, "description": "Lunisolar semidiurnal"},
    "K1": {"period_hours": 23.9345, "description": "Lunisolar diurnal"},
    "O1": {"period_hours": 25.8193, "description": "Principal lunar diurnal"},
    "P1": {"period_hours": 24.0659, "description": "Principal solar diurnal"},
    "Q1": {"period_hours": 26.8684, "description": "Larger lunar elliptic diurnal"},
    "M4": {"period_hours": 6.2103, "description": "Shallow water overtide of M2"},
    "M6": {"period_hours": 4.1402, "description": "Shallow water overtide of M2"},
    "MS4": {"period_hours": 6.1033, "description": "Shallow water compound tide"},
    "MN4": {"period_hours": 6.2692, "description": "Shallow water compound tide"},
    "2N2": {
        "period_hours": 12.9054,
        "description": "Lunar elliptic semidiurnal second-order",
    },
    "S1": {"period_hours": 24.0000, "description": "Solar diurnal"},
    "MF": {"period_hours": 327.8600, "description": "Lunisolar fortnightly"},
    "MM": {"period_hours": 661.3000, "description": "Lunar monthly"},
    "SSA": {"period_hours": 4382.9000, "description": "Solar semiannual"},
    "SA": {"period_hours": 8765.8000, "description": "Solar annual"},
}


# Vertical grid types
VGRID_TYPES: dict[int, dict] = {
    1: {
        "name": "LSC2",
        "description": "Localized sigma coordinates with shaved cells. Each node can have different number of layers.",
    },
    2: {
        "name": "SZ",
        "description": "Hybrid S-Z coordinates. S-layers near surface, Z-layers below. Good for deep ocean.",
    },
}


# Boundary condition types for bctides.in
BC_TYPES: dict[int, dict] = {
    0: {"name": "none", "description": "No boundary condition"},
    1: {
        "name": "time_history",
        "description": "Time history of elevation/velocity from elev2D.th",
    },
    2: {"name": "constant", "description": "Constant value specified in bctides.in"},
    3: {"name": "tidal", "description": "Tidal forcing with constituents"},
    4: {
        "name": "space_time",
        "description": "Spatial and temporal variation from .th file",
    },
    5: {"name": "combination", "description": "Tidal + time history (3+1 combined)"},
}


# SCHISM param.nml parameter reference (30+ parameters)
SCHISM_PARAMETERS: dict[str, dict] = {
    "dt": {
        "section": NamelistSection.CORE,
        "description": "Time step in seconds. Must satisfy CFL condition for the grid.",
        "type": "float",
        "units": "seconds",
        "typical_range": [60.0, 200.0],
        "default": 100.0,
        "common_errors": [
            "Too large for the grid resolution",
            "Not divisible into nspool or ihfskip",
        ],
    },
    "rnday": {
        "section": NamelistSection.CORE,
        "description": "Total run duration in days.",
        "type": "float",
        "units": "days",
        "typical_range": [1.0, 365.0],
        "default": 30.0,
        "common_errors": ["Exceeding available forcing data period"],
    },
    "ihfskip": {
        "section": NamelistSection.CORE,
        "description": "Stack skip count — number of timesteps per output stack. Controls output file size.",
        "type": "int",
        "typical_range": [864, 86400],
        "default": 864,
        "common_errors": [
            "Not divisible by nspool",
            "Too small creating too many output files",
        ],
    },
    "nhot": {
        "section": NamelistSection.CORE,
        "description": "Hot start flag. 0=cold start, 1=read hotstart.nc.",
        "type": "int",
        "valid_values": [0, 1],
        "default": 0,
        "common_errors": [
            "nhot=1 but hotstart.nc missing or incompatible",
            "nhot=1 with mismatched grid or parameters",
        ],
    },
    "nhot_write": {
        "section": NamelistSection.CORE,
        "description": "Hot start write flag. 1=write hotstart at ihfskip intervals.",
        "type": "int",
        "valid_values": [0, 1],
        "default": 1,
        "common_errors": [],
    },
    "ibc": {
        "section": NamelistSection.CORE,
        "description": "Baroclinic model flag. 0=barotropic, 1=baroclinic.",
        "type": "int",
        "valid_values": [0, 1],
        "default": 0,
        "common_errors": ["ibc=1 without proper T/S initialization"],
    },
    "ibtp": {
        "section": NamelistSection.CORE,
        "description": "Barotropic/baroclinic coupling. 0=no, 1=yes.",
        "type": "int",
        "valid_values": [0, 1],
        "default": 0,
        "common_errors": [],
    },
    "ics": {
        "section": NamelistSection.CORE,
        "description": "Coordinate system. 1=Cartesian, 2=lon/lat (spherical).",
        "type": "int",
        "valid_values": [1, 2],
        "default": 2,
        "common_errors": ["Mismatch with hgrid.gr3 coordinate system"],
    },
    "nramp": {
        "section": NamelistSection.CORE,
        "description": "Ramp-up flag for tidal forcing. 0=no ramp, 1=linear ramp.",
        "type": "int",
        "valid_values": [0, 1],
        "default": 1,
        "common_errors": ["nramp=0 causing initial shock with tidal forcing"],
    },
    "dramp": {
        "section": NamelistSection.CORE,
        "description": "Ramp-up period in days. Duration over which tidal forcing is ramped.",
        "type": "float",
        "units": "days",
        "typical_range": [1.0, 10.0],
        "default": 1.0,
        "common_errors": ["Too short for long-period constituents"],
    },
    "nrampbc": {
        "section": NamelistSection.CORE,
        "description": "Ramp flag for baroclinic forcing. 0=no ramp, 1=linear ramp.",
        "type": "int",
        "valid_values": [0, 1],
        "default": 0,
        "common_errors": [],
    },
    "drampbc": {
        "section": NamelistSection.CORE,
        "description": "Ramp period for baroclinic forcing in days.",
        "type": "float",
        "units": "days",
        "typical_range": [0.0, 5.0],
        "default": 0.0,
        "common_errors": [],
    },
    "itur": {
        "section": NamelistSection.OPT,
        "description": "Turbulence closure model. 0=none, 2=zero-equation, 3=k-omega, 4=k-epsilon, -1=GOTM.",
        "type": "int",
        "valid_values": [-1, 0, 2, 3, 4],
        "default": 0,
        "common_errors": [
            "Using 3D turbulence model (itur=3/4) in 2D mode",
            "itur=-1 without GOTM compiled",
        ],
    },
    "dfv0": {
        "section": NamelistSection.OPT,
        "description": "Vertical diffusivity minimum (m^2/s).",
        "type": "float",
        "units": "m^2/s",
        "typical_range": [1e-6, 1e-2],
        "default": 1e-2,
        "common_errors": ["Too large causing over-diffusion"],
    },
    "dfh0": {
        "section": NamelistSection.OPT,
        "description": "Horizontal diffusivity minimum (m^2/s).",
        "type": "float",
        "units": "m^2/s",
        "typical_range": [1e-6, 1e-2],
        "default": 1e-4,
        "common_errors": [],
    },
    "indvel": {
        "section": NamelistSection.OPT,
        "description": "Depth-induced breaking velocity. 0=off, 1=on.",
        "type": "int",
        "valid_values": [0, 1],
        "default": 0,
        "common_errors": [],
    },
    "nws": {
        "section": NamelistSection.OPT,
        "description": "Wind/atmospheric forcing type. 0=none, 1=constant, 2=spatially varying from sflux/.",
        "type": "int",
        "valid_values": [0, 1, 2, 3, 4],
        "default": 0,
        "common_errors": [
            "nws=2 but sflux/ directory missing or incomplete",
            "Temporal gaps in sflux files",
        ],
    },
    "wtiminc": {
        "section": NamelistSection.OPT,
        "description": "Time step for wind input in seconds. Must be >= dt.",
        "type": "float",
        "units": "seconds",
        "typical_range": [100.0, 3600.0],
        "default": 150.0,
        "common_errors": ["wtiminc < dt causing interpolation issues"],
    },
    "nrampwind": {
        "section": NamelistSection.OPT,
        "description": "Ramp flag for wind forcing. 0=no ramp, 1=linear ramp.",
        "type": "int",
        "valid_values": [0, 1],
        "default": 1,
        "common_errors": [],
    },
    "drampwind": {
        "section": NamelistSection.OPT,
        "description": "Ramp period for wind forcing in days.",
        "type": "float",
        "units": "days",
        "typical_range": [1.0, 5.0],
        "default": 1.0,
        "common_errors": [],
    },
    "iwindoff": {
        "section": NamelistSection.OPT,
        "description": "Flag for turning off wind during initial period.",
        "type": "int",
        "valid_values": [0, 1],
        "default": 0,
        "common_errors": [],
    },
    "slam0": {
        "section": NamelistSection.OPT,
        "description": "Center longitude for CPP projection (degrees). Must match domain center when ics=2.",
        "type": "float",
        "units": "degrees",
        "typical_range": [-180.0, 180.0],
        "default": -124.0,
        "common_errors": ["Not centered on model domain"],
    },
    "sfea0": {
        "section": NamelistSection.OPT,
        "description": "Center latitude for CPP projection (degrees). Must match domain center when ics=2.",
        "type": "float",
        "units": "degrees",
        "typical_range": [-90.0, 90.0],
        "default": 45.0,
        "common_errors": ["Not centered on model domain"],
    },
    "h0": {
        "section": NamelistSection.OPT,
        "description": "Minimum depth in meters. Nodes below this are treated as dry.",
        "type": "float",
        "units": "meters",
        "typical_range": [0.01, 1.0],
        "default": 0.01,
        "common_errors": ["Too small causing wetting/drying instability"],
    },
    "rmin": {
        "section": NamelistSection.OPT,
        "description": "Minimum bottom friction coefficient.",
        "type": "float",
        "typical_range": [0.0001, 0.01],
        "default": 0.0001,
        "common_errors": [],
    },
    "hmin_man": {
        "section": NamelistSection.OPT,
        "description": "Depth threshold for Manning's formula application in meters.",
        "type": "float",
        "units": "meters",
        "typical_range": [0.5, 2.0],
        "default": 1.0,
        "common_errors": [],
    },
    "ncor": {
        "section": NamelistSection.OPT,
        "description": "Coriolis flag. 0=off, 1=spatially varying (from ics=2).",
        "type": "int",
        "valid_values": [0, 1],
        "default": 1,
        "common_errors": ["ncor=0 for large domains where Coriolis matters"],
    },
    "nspool": {
        "section": NamelistSection.SCHOUT,
        "description": "Global output spool interval in timesteps. Must evenly divide ihfskip.",
        "type": "int",
        "typical_range": [1, 1000],
        "default": 36,
        "common_errors": [
            "nspool does not evenly divide ihfskip",
            "Too small causing excessive I/O",
        ],
    },
    "iof_hydro(1)": {
        "section": NamelistSection.SCHOUT,
        "description": "Output flag for elevation (eta2). 0=off, 1=on.",
        "type": "int",
        "valid_values": [0, 1],
        "default": 1,
        "common_errors": [],
    },
    "iof_hydro(16)": {
        "section": NamelistSection.SCHOUT,
        "description": "Output flag for horizontal velocity at nodes. 0=off, 1=on.",
        "type": "int",
        "valid_values": [0, 1],
        "default": 0,
        "common_errors": [],
    },
    "iof_hydro(19)": {
        "section": NamelistSection.SCHOUT,
        "description": "Output flag for depth-averaged velocity. 0=off, 1=on.",
        "type": "int",
        "valid_values": [0, 1],
        "default": 0,
        "common_errors": [],
    },
    "iof_hydro(26)": {
        "section": NamelistSection.SCHOUT,
        "description": "Output flag for wind speed. 0=off, 1=on.",
        "type": "int",
        "valid_values": [0, 1],
        "default": 0,
        "common_errors": [],
    },
    "iof_hydro(27)": {
        "section": NamelistSection.SCHOUT,
        "description": "Output flag for wind stress. 0=off, 1=on.",
        "type": "int",
        "valid_values": [0, 1],
        "default": 0,
        "common_errors": [],
    },
}


# Known SCHISM error patterns for diagnosis
SCHISM_ERROR_PATTERNS: list[dict] = [
    {
        "keywords": ["dry", "depth", "drying", "wetting", "negative depth"],
        "diagnosis": "Wetting/drying instability — nodes cycling between wet and dry states, or negative depths occurring.",
        "fixes": [
            "Increase h0 (minimum depth threshold)",
            "Reduce dt (timestep)",
            "Check bathymetry near coastline for abrupt changes",
            "Verify hgrid.gr3 has adequate resolution near wetting/drying fronts",
        ],
    },
    {
        "keywords": ["NaN", "nan", "infinity", "inf", "diverge"],
        "diagnosis": "Numerical divergence — solution blowing up, often from CFL violation or bad forcing.",
        "fixes": [
            "Reduce dt",
            "Check for extreme bathymetry values in hgrid.gr3",
            "Verify forcing data (sflux, bctides) for discontinuities",
            "Check vgrid.in for appropriate layer distribution",
        ],
    },
    {
        "keywords": ["hotstart", "hot start", "hotstart.nc", "nhot"],
        "diagnosis": "Hot start incompatibility — hotstart.nc doesn't match current configuration.",
        "fixes": [
            "Verify hotstart.nc was generated with same grid",
            "Check that nhot_write=1 in previous run",
            "Ensure param.nml parameters match between runs",
            "For changing grids, interpolate hotstart to new grid",
        ],
    },
    {
        "keywords": ["sflux", "wind", "atmospheric", "nws"],
        "diagnosis": "Atmospheric forcing error — missing or malformed sflux files.",
        "fixes": [
            "Verify sflux/ directory contains sflux_air_1.*.nc files",
            "Check temporal coverage spans simulation period",
            "Ensure nws=2 in param.nml for sflux-based forcing",
            "Check wtiminc matches sflux time step",
        ],
    },
    {
        "keywords": ["bctides", "tidal", "boundary", "open boundary"],
        "diagnosis": "Boundary condition error — bctides.in is inconsistent with hgrid.gr3 boundaries.",
        "fixes": [
            "Verify number of open boundaries in bctides.in matches hgrid.gr3",
            "Check tidal constituent specifications",
            "Ensure boundary node counts match between files",
            "Verify boundary condition type flags",
        ],
    },
    {
        "keywords": ["vgrid", "vertical", "layer", "level", "sigma"],
        "diagnosis": "Vertical grid error — vgrid.in is incompatible or has bad layer spacing.",
        "fixes": [
            "Verify vgrid type (1=LSC2, 2=SZ) matches intended setup",
            "Check layer spacing is monotonic",
            "For SZ, ensure transition depth is reasonable",
            "Verify number of levels matches param.nml expectations",
        ],
    },
    {
        "keywords": ["WWM", "wave", "wwm", "WWAVE"],
        "diagnosis": "WWM wave coupling error — Wind Wave Model setup issue.",
        "fixes": [
            "Verify wwminput.nml exists and is properly configured",
            "Check that WWM grid matches SCHISM grid",
            "Ensure wave boundary conditions are specified",
            "Verify SCHISM was compiled with WWM support",
        ],
    },
    {
        "keywords": ["nspool", "ihfskip", "output", "divisible"],
        "diagnosis": "Output configuration error — nspool/ihfskip mismatch.",
        "fixes": [
            "Ensure ihfskip is evenly divisible by nspool",
            "Check that ihfskip * dt gives desired output stack duration",
            "Typical: nspool=36 (1 hour at dt=100s), ihfskip=864 (1 day)",
        ],
    },
    {
        "keywords": ["memory", "allocation", "segfault", "SIGSEGV", "out of memory"],
        "diagnosis": "Memory error — grid too large or too many output variables requested.",
        "fixes": [
            "Reduce number of output variables (iof_hydro flags)",
            "Increase number of MPI processes",
            "Check for corrupted input files",
            "Verify grid size vs available memory",
        ],
    },
    {
        "keywords": ["MPI", "mpi", "parallel", "decomposition", "NPROC"],
        "diagnosis": "MPI/parallel execution error — domain decomposition or communication issue.",
        "fixes": [
            "Run with fewer MPI processes if grid is small",
            "Check that SCHISM was compiled with correct MPI library",
            "Verify that all input files are accessible from all MPI ranks",
            "Try running in serial first to isolate the issue",
        ],
    },
]
