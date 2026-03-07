"""Constants, enums, column definitions, and unit converters for NDBC data."""

from enum import Enum

# ---------------------------------------------------------------------------
# NDBC API URLs
# ---------------------------------------------------------------------------

REALTIME2_BASE = "https://www.ndbc.noaa.gov/data/realtime2"
ACTIVE_STATIONS_URL = "https://www.ndbc.noaa.gov/activestations.xml"

# Station cache TTL in seconds (10 minutes)
STATION_CACHE_TTL = 600

# ---------------------------------------------------------------------------
# Missing value sentinels used in NDBC fixed-width text files
# ---------------------------------------------------------------------------

MISSING_VALUES = {"MM", "99.0", "99.00", "999", "999.0", "9999", "9999.0"}

# ---------------------------------------------------------------------------
# Standard meteorological columns in realtime2 .txt files
# ---------------------------------------------------------------------------

STANDARD_COLUMNS = [
    "YY",
    "MM",
    "DD",
    "hh",
    "mm",
    "WDIR",
    "WSPD",
    "GST",
    "WVHT",
    "DPD",
    "APD",
    "MWD",
    "PRES",
    "ATMP",
    "WTMP",
    "DEWP",
    "VIS",
    "PTDY",
    "TIDE",
]

COLUMN_LABELS = {
    "WDIR": "Wind Dir (\u00b0T)",
    "WSPD": "Wind Spd (m/s)",
    "GST": "Gust (m/s)",
    "WVHT": "Wave Ht (m)",
    "DPD": "Dom Period (s)",
    "APD": "Avg Period (s)",
    "MWD": "Mean Wave Dir (\u00b0T)",
    "PRES": "Pressure (hPa)",
    "ATMP": "Air Temp (\u00b0C)",
    "WTMP": "Water Temp (\u00b0C)",
    "DEWP": "Dew Point (\u00b0C)",
    "VIS": "Visibility (nmi)",
    "PTDY": "Pres Tend (hPa)",
    "TIDE": "Tide (ft)",
}

COLUMN_DESCRIPTIONS = {
    "WDIR": "Wind direction (degrees true, clockwise from north)",
    "WSPD": "Sustained wind speed (m/s)",
    "GST": "Peak gust speed in 8-minute window (m/s)",
    "WVHT": "Significant wave height (m)",
    "DPD": "Dominant wave period (s)",
    "APD": "Average wave period (s)",
    "MWD": "Mean wave direction (degrees true)",
    "PRES": "Sea level pressure (hPa)",
    "ATMP": "Air temperature (\u00b0C)",
    "WTMP": "Sea surface temperature (\u00b0C)",
    "DEWP": "Dewpoint temperature (\u00b0C)",
    "VIS": "Station visibility (nautical miles)",
    "PTDY": "Pressure tendency over 3 hours (hPa)",
    "TIDE": "Water level (ft above MLLW)",
}

# Variables suitable for daily summaries (numeric, physically meaningful)
SUMMARY_VARIABLES = ["WSPD", "GST", "WVHT", "DPD", "PRES", "ATMP", "WTMP"]


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StationType(str, Enum):
    """NDBC station platform types from activestations.xml."""

    BUOY = "buoy"
    FIXED = "fixed"
    OTHER = "other"
    DART = "dart"
    OIL_RIG = "oilrig"
    TIDES = "tides"
    CMAN = "cman"


class DataFile(str, Enum):
    """Realtime2 data file extensions."""

    TXT = "txt"  # Standard meteorological
    SPEC = "spec"  # Spectral wave summary
    DRIFT = "drift"  # Drifting buoy
    CWIND = "cwind"  # Continuous wind
    OCEAN = "ocean"  # Oceanographic (salinity, O2, etc.)


# ---------------------------------------------------------------------------
# Compass direction conversion
# ---------------------------------------------------------------------------

_COMPASS_POINTS = [
    "N",
    "NNE",
    "NE",
    "ENE",
    "E",
    "ESE",
    "SE",
    "SSE",
    "S",
    "SSW",
    "SW",
    "WSW",
    "W",
    "WNW",
    "NW",
    "NNW",
]


def degrees_to_compass(degrees: float | None) -> str:
    """Convert wind/wave direction in degrees to 16-point compass."""
    if degrees is None:
        return "---"
    idx = round(degrees / 22.5) % 16
    return _COMPASS_POINTS[idx]


# ---------------------------------------------------------------------------
# Unit converters
# ---------------------------------------------------------------------------


def ms_to_knots(ms: float) -> float:
    """Convert m/s to knots."""
    return ms * 1.94384


def celsius_to_fahrenheit(c: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return c * 9.0 / 5.0 + 32.0


def hpa_to_inhg(hpa: float) -> float:
    """Convert hPa (mbar) to inches of mercury."""
    return hpa / 33.8639


def m_to_ft(m: float) -> float:
    """Convert metres to feet."""
    return m * 3.28084
