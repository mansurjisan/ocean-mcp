"""Embedded domain knowledge for ADCIRC model configuration."""

from enum import Enum

ADCIRC_WIKI_BASE = "https://wiki.adcirc.org"


class ParamCategory(str, Enum):
    """Categories for fort.15 parameters."""

    TIME_STEPPING = "time_stepping"
    FORCING = "forcing"
    FRICTION = "friction"
    OUTPUT = "output"
    TIDAL = "tidal"
    SOLVER = "solver"
    WETTING_DRYING = "wetting_drying"
    SPATIAL = "spatial"
    METEOROLOGICAL = "meteorological"
    WAVE_COUPLING = "wave_coupling"


# Tidal constituent reference
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


# NWS meteorological forcing types
NWS_VALUES: dict[int, dict] = {
    0: {"description": "No meteorological forcing", "files_required": []},
    1: {
        "description": "Spatially constant pressure and wind from fort.22",
        "files_required": ["fort.22"],
    },
    2: {
        "description": "Spatially constant pressure and wind from fort.22 (alternate format)",
        "files_required": ["fort.22"],
    },
    5: {
        "description": "Spatially varying wind and pressure on a regular grid (fort.22 OWI format)",
        "files_required": ["fort.221", "fort.222"],
    },
    6: {
        "description": "Spatially varying wind and pressure on a regular grid (fort.22 OWI alternate)",
        "files_required": ["fort.221", "fort.222"],
    },
    8: {
        "description": "Holland parametric hurricane model using fort.22 (ATCF best track)",
        "files_required": ["fort.22"],
    },
    9: {
        "description": "Asymmetric hurricane vortex model from fort.22",
        "files_required": ["fort.22"],
    },
    10: {
        "description": "Spatially varying wind and pressure from 10m winds (fort.22 OWI)",
        "files_required": ["fort.221", "fort.222"],
    },
    12: {
        "description": "OWI format wind and pressure with time interpolation",
        "files_required": ["fort.221", "fort.222"],
    },
    -12: {
        "description": "OWI format with blank snaps for ramp-up (negative NWS convention)",
        "files_required": ["fort.221", "fort.222"],
    },
    15: {
        "description": "HWind snapshot wind fields",
        "files_required": ["fort.22"],
    },
    16: {
        "description": "GAHM generalized asymmetric Holland model",
        "files_required": ["fort.22"],
    },
    19: {
        "description": "Asymmetric vortex with wind averaging",
        "files_required": ["fort.22"],
    },
    20: {
        "description": "Generalized asymmetric vortex + background wind merge",
        "files_required": ["fort.22"],
    },
}


# Nodal attribute reference (fort.13)
NODAL_ATTRIBUTES: dict[str, dict] = {
    "primitive_weighting_in_continuity_equation": {
        "description": "Tau0 spatial variation for GWCE weighting. Controls lumped vs consistent mass matrix.",
        "units": "dimensionless",
        "typical_range": [0.005, 0.1],
        "default_value": 0.03,
    },
    "mannings_n_at_sea_floor": {
        "description": "Manning's n friction coefficient at the sea floor.",
        "units": "s/m^(1/3)",
        "typical_range": [0.01, 0.20],
        "default_value": 0.025,
    },
    "surface_submergence_state": {
        "description": "Initial wetting/drying state. 1=wet start, 0=dry start.",
        "units": "flag",
        "typical_range": [0, 1],
        "default_value": 1,
    },
    "surface_directional_effective_roughness_length": {
        "description": "Directional wind reduction factors for land roughness (12 directions).",
        "units": "dimensionless",
        "typical_range": [0.0, 1.0],
        "default_value": 0.0,
    },
    "surface_canopy_coefficient": {
        "description": "Fraction of canopy coverage for wind sheltering.",
        "units": "dimensionless",
        "typical_range": [0.0, 1.0],
        "default_value": 1.0,
    },
    "bridge_pilings_friction_paramenters": {
        "description": "Bridge piling drag parameters (BKFric, BAlpha, BDelX, PTEFAC).",
        "units": "mixed",
        "typical_range": [0.0, 10.0],
        "default_value": 0.0,
    },
    "elemental_slope_limiter": {
        "description": "Controls the slope limiter for wetting/drying stability.",
        "units": "dimensionless",
        "typical_range": [0.0, 0.05],
        "default_value": 0.0,
    },
    "advection_state": {
        "description": "Controls whether advection is applied at each node. 0=off, 1=on.",
        "units": "flag",
        "typical_range": [0, 1],
        "default_value": 1,
    },
    "average_horizontal_eddy_viscosity_in_sea_water_wrt_depth": {
        "description": "Spatially varying horizontal eddy viscosity.",
        "units": "m^2/s",
        "typical_range": [1.0, 50.0],
        "default_value": 5.0,
    },
    "sea_surface_height_above_geoid": {
        "description": "Initial water surface elevation offset from geoid.",
        "units": "m",
        "typical_range": [-1.0, 1.0],
        "default_value": 0.0,
    },
}


# Fort.15 parameter reference (30+ parameters)
ADCIRC_PARAMETERS: dict[str, dict] = {
    "RUNDES": {
        "description": "Run description (32 characters max). Descriptive title for the simulation.",
        "category": ParamCategory.SOLVER,
        "type": "string",
        "line": 1,
        "common_errors": ["Exceeding 32-character limit"],
    },
    "RUNID": {
        "description": "Run ID (24 characters max). Short identifier for output file naming.",
        "category": ParamCategory.SOLVER,
        "type": "string",
        "line": 2,
        "common_errors": ["Exceeding 24-character limit"],
    },
    "NFOVER": {
        "description": "Nonfatal error override. 0=stop on nonfatal errors, 1=continue.",
        "category": ParamCategory.SOLVER,
        "type": "int",
        "valid_values": [0, 1],
        "typical_range": [0, 1],
        "common_errors": ["Using 1 in production runs masks real problems"],
    },
    "NABOUT": {
        "description": "Abreviated output flag. -1=full, 0=brief, 1=none.",
        "category": ParamCategory.OUTPUT,
        "type": "int",
        "valid_values": [-1, 0, 1],
        "typical_range": [-1, 1],
        "common_errors": [],
    },
    "NSCREEN": {
        "description": "Screen output frequency (time steps). 0=no screen output.",
        "category": ParamCategory.OUTPUT,
        "type": "int",
        "typical_range": [0, 10000],
        "common_errors": ["Setting too low causes I/O bottleneck"],
    },
    "IHOT": {
        "description": "Hot start flag. 0=cold start, 67=read fort.67, 68=read fort.68.",
        "category": ParamCategory.SOLVER,
        "type": "int",
        "valid_values": [0, 67, 68],
        "common_errors": [
            "Using IHOT=67/68 without corresponding hot start file",
            "Wind ramp not matching hot start time",
        ],
    },
    "ICS": {
        "description": "Coordinate system. 1=Cartesian, 2=spherical (lon/lat).",
        "category": ParamCategory.SPATIAL,
        "type": "int",
        "valid_values": [1, 2],
        "common_errors": ["Using Cartesian (1) with geographic mesh"],
    },
    "IM": {
        "description": "Model type. 0=2DDI barotropic, 1=3D baroclinic, 2=3D barotropic, 10=2DDI with transport, 11111=lumped GWCE explicit.",
        "category": ParamCategory.SOLVER,
        "type": "int",
        "valid_values": [0, 1, 2, 10, 11111, 21112, 31111],
        "common_errors": ["Wrong IM for intended physics"],
    },
    "NOLIBF": {
        "description": "Bottom friction type. 0=linear, 1=quadratic, 2=hybrid nonlinear with spatially varying.",
        "category": ParamCategory.FRICTION,
        "type": "int",
        "valid_values": [0, 1, 2],
        "common_errors": [
            "Using NOLIBF=2 without fort.13 Manning's n attribute",
        ],
    },
    "NOLIFA": {
        "description": "Finite amplitude terms. 0=no, 1=yes, 2=yes with wetting/drying.",
        "category": ParamCategory.WETTING_DRYING,
        "type": "int",
        "valid_values": [0, 1, 2],
        "common_errors": ["Must be 2 for wetting/drying simulations"],
    },
    "NOLICA": {
        "description": "Spatial advection terms. 0=no, 1=yes.",
        "category": ParamCategory.SOLVER,
        "type": "int",
        "valid_values": [0, 1],
        "common_errors": [],
    },
    "NOLICAT": {
        "description": "Time derivative advection terms. 0=no, 1=yes.",
        "category": ParamCategory.SOLVER,
        "type": "int",
        "valid_values": [0, 1],
        "common_errors": [],
    },
    "NWP": {
        "description": "Number of nodal attributes in fort.13. Must match the fort.13 file.",
        "category": ParamCategory.SPATIAL,
        "type": "int",
        "typical_range": [0, 20],
        "common_errors": ["Mismatch between NWP value and fort.13 attribute count"],
        "companion_files": ["fort.13"],
    },
    "NCOR": {
        "description": "Coriolis forcing. 0=no Coriolis, 1=spatially constant, 2=spatially variable (latitude-based).",
        "category": ParamCategory.FORCING,
        "type": "int",
        "valid_values": [0, 1, 2],
        "common_errors": [
            "Using NCOR=1 for large domains where spatially variable is needed"
        ],
    },
    "NTIP": {
        "description": "Tidal potential forcing. 0=no, 1=tidal potential, 2=tidal potential + self-attraction/loading.",
        "category": ParamCategory.TIDAL,
        "type": "int",
        "valid_values": [0, 1, 2],
        "common_errors": [],
    },
    "NWS": {
        "description": "Wind stress and pressure forcing type. Controls meteorological input format. See NWS_VALUES for all types.",
        "category": ParamCategory.METEOROLOGICAL,
        "type": "int",
        "valid_values": list(NWS_VALUES.keys()),
        "common_errors": [
            "NWS/fort.22 format mismatch",
            "Missing companion meteorological files",
            "Not using negative NWS for cold start with met forcing",
        ],
        "companion_files": ["fort.22", "fort.221", "fort.222"],
    },
    "NRAMP": {
        "description": "Ramp function type. 0=no ramp, 1=linear ramp. Controls how forcing is applied during spin-up.",
        "category": ParamCategory.FORCING,
        "type": "int",
        "valid_values": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
        "common_errors": ["Insufficient ramp duration causing instability"],
    },
    "G": {
        "description": "Gravitational acceleration constant (m/s^2).",
        "category": ParamCategory.SOLVER,
        "type": "float",
        "units": "m/s^2",
        "typical_range": [9.80, 9.82],
        "common_errors": ["Wrong units when using non-standard coordinate system"],
    },
    "TAU0": {
        "description": "GWCE weighting factor. Controls balance between wave and primitive equations. Negative values enable spatially varying tau0 from fort.13.",
        "category": ParamCategory.SOLVER,
        "type": "float",
        "typical_range": [-3.0, 0.1],
        "common_errors": [
            "TAU0 too large causes excessive damping",
            "TAU0 too small causes noise/instability",
        ],
    },
    "DTDP": {
        "description": "Time step in seconds. Must satisfy CFL condition: DTDP < dx_min / sqrt(g * h_max).",
        "category": ParamCategory.TIME_STEPPING,
        "type": "float",
        "units": "seconds",
        "typical_range": [0.5, 60.0],
        "common_errors": [
            "CFL violation (timestep too large for mesh resolution)",
            "Unnecessarily small timestep wasting compute time",
        ],
    },
    "STATIM": {
        "description": "Starting simulation time (days). Usually 0.0 for cold start.",
        "category": ParamCategory.TIME_STEPPING,
        "type": "float",
        "units": "days",
        "typical_range": [0.0, 0.0],
        "common_errors": ["Non-zero STATIM with IHOT=0 (cold start)"],
    },
    "REFTIM": {
        "description": "Reference time (days). Usually 0.0.",
        "category": ParamCategory.TIME_STEPPING,
        "type": "float",
        "units": "days",
        "typical_range": [0.0, 0.0],
        "common_errors": [],
    },
    "RNDAY": {
        "description": "Total run duration in days.",
        "category": ParamCategory.TIME_STEPPING,
        "type": "float",
        "units": "days",
        "typical_range": [1.0, 365.0],
        "common_errors": ["RNDAY not covering the full event period"],
    },
    "DRAMP": {
        "description": "Ramp duration in days. Time over which forcing is gradually applied. Should be >= 1 tidal cycle for tidal runs.",
        "category": ParamCategory.FORCING,
        "type": "float",
        "units": "days",
        "typical_range": [0.5, 10.0],
        "common_errors": [
            "DRAMP shorter than longest tidal period",
            "DRAMP=0 with tidal forcing causing shock",
        ],
    },
    "H0": {
        "description": "Minimum water depth for wetting/drying (meters). Nodes shallower than H0 are treated as dry.",
        "category": ParamCategory.WETTING_DRYING,
        "type": "float",
        "units": "meters",
        "typical_range": [0.01, 0.5],
        "common_errors": [
            "H0 too small causes instability",
            "H0 too large suppresses real flooding",
        ],
    },
    "SLAM0": {
        "description": "Center of projection longitude (degrees, CPP projection). Used with ICS=2.",
        "category": ParamCategory.SPATIAL,
        "type": "float",
        "units": "degrees",
        "typical_range": [-180.0, 180.0],
        "common_errors": ["Not centering on domain"],
    },
    "SFEA0": {
        "description": "Center of projection latitude (degrees, CPP projection). Used with ICS=2.",
        "category": ParamCategory.SPATIAL,
        "type": "float",
        "units": "degrees",
        "typical_range": [-90.0, 90.0],
        "common_errors": ["Not centering on domain"],
    },
    "CF": {
        "description": "Bottom friction coefficient. Used when NOLIBF=0 (linear) or NOLIBF=1 (quadratic, uniform).",
        "category": ParamCategory.FRICTION,
        "type": "float",
        "typical_range": [0.0001, 0.01],
        "common_errors": ["CF too large over-damps the solution"],
    },
    "ESLM": {
        "description": "Horizontal eddy viscosity (m^2/s). Negative value enables Smagorinsky model.",
        "category": ParamCategory.SOLVER,
        "type": "float",
        "units": "m^2/s",
        "typical_range": [-0.5, 50.0],
        "common_errors": ["ESLM too large over-smooths the solution"],
    },
    "CORI": {
        "description": "Coriolis parameter (1/s). Only used when NCOR=1.",
        "category": ParamCategory.FORCING,
        "type": "float",
        "units": "1/s",
        "typical_range": [0.0, 0.00015],
        "common_errors": ["Forgetting to set when NCOR=1"],
    },
    "NTIF": {
        "description": "Number of tidal forcing frequencies (tidal potential constituents).",
        "category": ParamCategory.TIDAL,
        "type": "int",
        "typical_range": [0, 20],
        "common_errors": ["NTIF=0 when tidal forcing is expected"],
    },
    "NBFR": {
        "description": "Number of tidal boundary forcing frequencies.",
        "category": ParamCategory.TIDAL,
        "type": "int",
        "typical_range": [0, 20],
        "common_errors": ["NBFR mismatch with open boundary specification"],
    },
    "ANGINN": {
        "description": "Inner angle threshold for boundary node identification (degrees).",
        "category": ParamCategory.SPATIAL,
        "type": "float",
        "units": "degrees",
        "typical_range": [90.0, 180.0],
        "common_errors": [],
    },
    "NOUTE": {
        "description": "Station output flag for elevation. 0=no output, positive=output interval in timesteps.",
        "category": ParamCategory.OUTPUT,
        "type": "int",
        "typical_range": [0, 100000],
        "common_errors": ["NOUTE > 0 but no stations specified"],
    },
    "TOUTSE": {
        "description": "Start time for station elevation output (days).",
        "category": ParamCategory.OUTPUT,
        "type": "float",
        "units": "days",
        "common_errors": [],
    },
    "TOUTFE": {
        "description": "End time for station elevation output (days).",
        "category": ParamCategory.OUTPUT,
        "type": "float",
        "units": "days",
        "common_errors": ["TOUTFE < TOUTSE"],
    },
    "NSPOOLE": {
        "description": "Station elevation output interval in timesteps.",
        "category": ParamCategory.OUTPUT,
        "type": "int",
        "typical_range": [1, 10000],
        "common_errors": ["Output interval too small causing large files"],
    },
    "NSTAE": {
        "description": "Number of elevation recording stations.",
        "category": ParamCategory.OUTPUT,
        "type": "int",
        "typical_range": [0, 1000],
        "common_errors": ["NSTAE > 0 but missing station coordinates in fort.15"],
    },
}


# Known ADCIRC error patterns for diagnosis
ADCIRC_ERROR_PATTERNS: list[dict] = [
    {
        "keywords": ["CFL", "courant", "instability", "blew up", "NaN"],
        "diagnosis": "CFL condition violation — timestep is too large for the mesh resolution and water depth.",
        "fixes": [
            "Reduce DTDP (timestep)",
            "Check for overly small elements in the mesh (fort.14)",
            "Increase H0 (minimum depth) if wetting/drying is active",
            "Verify bathymetry for unrealistic deep spots",
        ],
    },
    {
        "keywords": ["hot start", "hotstart", "fort.67", "fort.68", "IHOT"],
        "diagnosis": "Hot start file error — the hot start file is missing, incompatible, or from a different mesh/configuration.",
        "fixes": [
            "Verify IHOT matches the hot start file type (67 or 68)",
            "Ensure the hot start file was generated by the same mesh (fort.14)",
            "Check that DTDP and other parameters match the generating run",
            "For wind restarts, ensure meteorological forcing continuity",
        ],
    },
    {
        "keywords": ["NWS", "wind", "meteorological", "fort.22", "pressure"],
        "diagnosis": "Meteorological forcing error — NWS value doesn't match the fort.22 format, or forcing files are missing.",
        "fixes": [
            "Verify NWS value matches your met file format",
            "Check that all required companion files exist (fort.221, fort.222 for OWI)",
            "Ensure temporal coverage of met data spans the simulation period",
            "For negative NWS, check that blank snaps cover the ramp-up period",
        ],
    },
    {
        "keywords": [
            "boundary",
            "open boundary",
            "elevation specified",
            "flux",
            "NBFR",
        ],
        "diagnosis": "Boundary condition error — mismatch between open boundary specification and forcing data.",
        "fixes": [
            "Verify NBFR matches the number of tidal constituents",
            "Check that open boundary nodes in fort.14 match fort.15 specification",
            "Ensure boundary condition type is appropriate (elevation vs flux)",
        ],
    },
    {
        "keywords": ["fort.13", "nodal attribute", "NWP", "manning"],
        "diagnosis": "Nodal attribute file error — fort.13 doesn't match expected attribute count or mesh nodes.",
        "fixes": [
            "Verify NWP in fort.15 matches number of attributes in fort.13",
            "Ensure fort.13 was generated for the same mesh (matching node count)",
            "Check attribute names are spelled exactly as ADCIRC expects",
        ],
    },
    {
        "keywords": ["wetting", "drying", "dry node", "H0", "NOLIFA"],
        "diagnosis": "Wetting/drying instability — elements cycling between wet and dry states.",
        "fixes": [
            "Increase H0 (minimum depth threshold)",
            "Ensure NOLIFA=2 for wetting/drying",
            "Add elemental_slope_limiter to fort.13",
            "Reduce timestep (DTDP)",
        ],
    },
    {
        "keywords": ["tau0", "GWCE", "mass balance", "conservation"],
        "diagnosis": "GWCE weighting issue — TAU0 value causing poor mass conservation or instability.",
        "fixes": [
            "Try TAU0=-3 for spatially varying (fulldomainCFL-based)",
            "Use fort.13 primitive_weighting_in_continuity_equation attribute",
            "Typical range: 0.005-0.05 for constant TAU0",
        ],
    },
    {
        "keywords": ["memory", "allocation", "segfault", "SIGSEGV"],
        "diagnosis": "Memory allocation failure — mesh too large for available RAM or array bounds exceeded.",
        "fixes": [
            "Check mesh size vs available memory",
            "Verify fort.14 node/element counts are correct",
            "Ensure MPI domain decomposition is appropriate",
            "Check for corrupted input files",
        ],
    },
    {
        "keywords": ["ramp", "DRAMP", "NRAMP", "spin-up", "spinup"],
        "diagnosis": "Ramp/spin-up issue — forcing applied too abruptly causing initial instability.",
        "fixes": [
            "Increase DRAMP to at least 1-2 tidal cycles",
            "Ensure NRAMP matches the type of ramping needed",
            "For meteorological forcing, use adequate met ramp duration",
        ],
    },
    {
        "keywords": ["tidal", "constituent", "NTIF", "NBFR", "harmonic"],
        "diagnosis": "Tidal constituent specification error — mismatch in tidal forcing setup.",
        "fixes": [
            "Verify NTIF and NBFR counts match actual constituent lists",
            "Check constituent names match ADCIRC's expected names exactly",
            "Ensure tidal potential and boundary forcing are consistent",
        ],
    },
]


# Fort.15 canonical line ordering (used by parser)
FORT15_LINE_ORDER: list[str] = [
    "RUNDES",
    "RUNID",
    "NFOVER",
    "NABOUT",
    "NSCREEN",
    "IHOT",
    "ICS",
    "IM",
    "NOLIBF_NOLIFA_NOLICA_NOLICAT",
    "NWP",
    # (NWP attribute names follow if NWP > 0)
    "NCOR",
    "NTIP",
    "NWS",
    "NRAMP",
    "G",
    "TAU0",  # or TAU0 TAU0FullDomainMin TAU0FullDomainMax if TAU0=-5
    "DTDP",
    "STATIM",
    "REFTIM",
    "RNDAY",
    "DRAMP",
    "A00_B00_C00",  # time weighting
    "H0_NODEDRYMIN_NODEWETMIN_VELMIN",
    "SLAM0_SFEA0",
    "CF",  # or ESLM depending on NOLIBF
    "ESLM",
    "CORI",
    "NTIF",
    # (tidal potential constituent lines follow)
    "NBFR",
    # (boundary forcing constituent lines follow)
    "ANGINN",
    # output sections follow
]
