"""Constants, enums, and helpers for winds-mcp."""

from enum import Enum


class Units(str, Enum):
    METRIC = "metric"
    ENGLISH = "english"


# NWS API base URL
NWS_API_BASE = "https://api.weather.gov"

# Iowa Environmental Mesonet base URL
IEM_BASE = "https://mesonet.agron.iastate.edu"

# User-Agent required by NWS API
USER_AGENT = "winds-mcp/0.1.0 (https://github.com/mansurjisan/ocean-mcp)"

# US state codes for validation
US_STATES = {
    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
    "DC": "District of Columbia",
    "PR": "Puerto Rico",
    "VI": "Virgin Islands",
    "GU": "Guam",
    "AS": "American Samoa",
    "MP": "Northern Mariana Islands",
}

# 16-point compass rose for wind direction
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
    """Convert wind direction in degrees to a 16-point compass string."""
    if degrees is None:
        return "---"
    idx = round(degrees / 22.5) % 16
    return _COMPASS_POINTS[idx]


# Unit conversion helpers


def ms_to_knots(ms: float) -> float:
    """Convert meters per second to knots."""
    return ms * 1.94384


def celsius_to_fahrenheit(c: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return c * 9.0 / 5.0 + 32.0


def pa_to_inhg(pa: float) -> float:
    """Convert Pascals to inches of mercury."""
    return pa / 3386.39


def m_to_miles(m: float) -> float:
    """Convert meters to statute miles."""
    return m / 1609.34


def kmh_to_knots(kmh: float) -> float:
    """Convert km/h to knots."""
    return kmh * 0.539957
