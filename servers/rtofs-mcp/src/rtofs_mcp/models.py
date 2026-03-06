"""Dataset registry, enums, and constants for RTOFS MCP server."""

from __future__ import annotations

from enum import Enum


class RTOFSDatasetType(str, Enum):
    """RTOFS dataset types on HYCOM THREDDS."""

    SURFACE_FORECAST = "surface_forecast"
    PROFILE_FORECAST = "profile_forecast"


class RTOFSVariable(str, Enum):
    """RTOFS surface variables."""

    SST = "sst"
    SSS = "sss"
    U_CURRENT = "u_current"
    V_CURRENT = "v_current"
    SSH = "ssh"


# HYCOM THREDDS NCSS base URL
THREDDS_BASE = "https://tds.hycom.org/thredds"

# NCSS endpoint template: {THREDDS_BASE}/ncss/{dataset_path}
# OPeNDAP endpoint template: {THREDDS_BASE}/dodsC/{dataset_path}

# ESPC-D-V02 datasets (operational HYCOM/RTOFS)
DATASETS = {
    "ssh": {
        "path": "FMRC_ESPC-D-V02_ssh/FMRC_ESPC-D-V02_ssh_best.ncd",
        "variables": {"surf_el": {"unit": "m", "long_name": "Sea Surface Height"}},
        "description": "Sea Surface Height, hourly, 8-day forecast",
        "dimensions": "2D",
    },
    "sst": {
        "path": "FMRC_ESPC-D-V02_t3z/FMRC_ESPC-D-V02_t3z_best.ncd",
        "variables": {"water_temp": {"unit": "degC", "long_name": "Water Temperature"}},
        "description": "Temperature (3D with depth), daily, 8-day forecast",
        "dimensions": "3D",
    },
    "sss": {
        "path": "FMRC_ESPC-D-V02_s3z/FMRC_ESPC-D-V02_s3z_best.ncd",
        "variables": {"salinity": {"unit": "PSU", "long_name": "Salinity"}},
        "description": "Salinity (3D with depth), daily, 8-day forecast",
        "dimensions": "3D",
    },
    "currents": {
        "path": "FMRC_ESPC-D-V02_uv3z/FMRC_ESPC-D-V02_uv3z_best.ncd",
        "variables": {
            "water_u": {"unit": "m/s", "long_name": "Eastward Current Velocity"},
            "water_v": {"unit": "m/s", "long_name": "Northward Current Velocity"},
        },
        "description": "Ocean currents u/v (3D with depth), daily, 8-day forecast",
        "dimensions": "3D",
    },
}

# User-friendly variable names -> THREDDS dataset key + variable name
SURFACE_VARIABLES = {
    "sst": {
        "dataset": "sst",
        "thredds_var": "water_temp",
        "unit": "degC",
        "long_name": "Sea Surface Temperature",
    },
    "sss": {
        "dataset": "sss",
        "thredds_var": "salinity",
        "unit": "PSU",
        "long_name": "Sea Surface Salinity",
    },
    "u_current": {
        "dataset": "currents",
        "thredds_var": "water_u",
        "unit": "m/s",
        "long_name": "Eastward Current Velocity",
    },
    "v_current": {
        "dataset": "currents",
        "thredds_var": "water_v",
        "unit": "m/s",
        "long_name": "Northward Current Velocity",
    },
    "ssh": {
        "dataset": "ssh",
        "thredds_var": "surf_el",
        "unit": "m",
        "long_name": "Sea Surface Height",
    },
}

PROFILE_VARIABLES = {
    "temperature": {
        "dataset": "sst",
        "thredds_var": "water_temp",
        "unit": "degC",
        "long_name": "Temperature",
    },
    "salinity": {
        "dataset": "sss",
        "thredds_var": "salinity",
        "unit": "PSU",
        "long_name": "Salinity",
    },
    "u": {
        "dataset": "currents",
        "thredds_var": "water_u",
        "unit": "m/s",
        "long_name": "Eastward Current Velocity",
    },
    "v": {
        "dataset": "currents",
        "thredds_var": "water_v",
        "unit": "m/s",
        "long_name": "Northward Current Velocity",
    },
}

# RTOFS/ESPC system specifications
RTOFS_SPECS = {
    "full_name": "Real-Time Ocean Forecast System (RTOFS) / ESPC-D-V02",
    "model_core": "HYCOM (HYbrid Coordinate Ocean Model)",
    "operator": "NOAA/NWS/NCEP + U.S. Navy NRL",
    "domain": "Global ocean (1/12 degree, ~8 km)",
    "horizontal_resolution": "1/12 degree (~8 km)",
    "vertical_levels": "40 layers (hybrid coordinates)",
    "forecast_length": "8 days (192 hours)",
    "update_cycle": "Daily (12z)",
    "surface_output": "Hourly SSH; daily SST, SSS, currents (all with depth)",
    "data_source": "HYCOM THREDDS (NCSS CSV + OPeNDAP)",
    "data_url": "https://tds.hycom.org/thredds/",
    "longitude_convention": "0 to 360 (NCSS accepts -180 to 180 and converts)",
    "forcing": "GFS/NAVGEM atmospheric forcing",
    "assimilation": "NCODA (Navy Coupled Ocean Data Assimilation)",
}
