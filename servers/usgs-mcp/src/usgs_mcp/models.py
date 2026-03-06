"""Constants and helpers for usgs-mcp."""

USGS_BASE_URL = "https://waterservices.usgs.gov/nwis"
USGS_PEAK_URL = "https://nwis.waterdata.usgs.gov/nwis/peak"

USER_AGENT = "usgs-mcp/0.1.0 (https://github.com/mansurjisan/ocean-mcp)"

# Well-known USGS parameter codes
PARAMETER_CODES: dict[str, dict] = {
    "00060": {
        "name": "Discharge",
        "units": "ft³/s (cfs)",
        "description": "Streamflow discharge",
    },
    "00065": {
        "name": "Gage height",
        "units": "ft",
        "description": "Water surface elevation above datum",
    },
    "00010": {"name": "Temperature", "units": "°C", "description": "Water temperature"},
    "00045": {
        "name": "Precipitation",
        "units": "in",
        "description": "Accumulated precipitation",
    },
    "00095": {
        "name": "Specific conductance",
        "units": "µS/cm",
        "description": "Specific conductance at 25°C",
    },
    "00300": {
        "name": "Dissolved oxygen",
        "units": "mg/L",
        "description": "Dissolved oxygen",
    },
    "00400": {"name": "pH", "units": "standard units", "description": "pH of water"},
    "63680": {"name": "Turbidity", "units": "FNU", "description": "Turbidity"},
}

# Well-known reference sites for testing and examples
REFERENCE_SITES: dict[str, dict] = {
    "01646500": {"name": "Potomac River at Little Falls, MD", "state": "MD"},
    "02037500": {"name": "James River at Richmond, VA", "state": "VA"},
    "07010000": {"name": "Mississippi River at St. Louis, MO", "state": "MO"},
    "08066500": {"name": "Trinity River at Romayor, TX", "state": "TX"},
    "02146000": {"name": "Catawba River near Pleasant Garden, NC", "state": "NC"},
}

# US state codes for site queries
US_STATE_CODES: dict[str, str] = {
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

# NWS flood stage categories
FLOOD_CATEGORIES: dict[str, str] = {
    "action": "Water is approaching bankfull; begin monitoring",
    "flood": "Minor flooding is occurring or imminent",
    "moderate": "Moderate flooding; some inundation of structures/roads",
    "major": "Major flooding; extensive inundation, significant threat to life/property",
}

# Stat report types
STAT_REPORT_TYPES: dict[str, str] = {
    "daily": "Daily statistics",
    "monthly": "Monthly statistics",
    "annual": "Annual statistics",
}

# USGS data qualification codes
QUALIFICATION_CODES: dict[str, str] = {
    "A": "Approved for publication",
    "P": "Provisional, subject to revision",
    "e": "Estimated",
    "Eqp": "Equipment malfunction",
    "Mnt": "Maintenance",
    "Dry": "Dry conditions",
    "Ssn": "Parameter monitored seasonally",
}


def format_parameter(code: str) -> str:
    """Return a human-readable name for a USGS parameter code."""
    info = PARAMETER_CODES.get(code)
    if info:
        return f"{info['name']} ({info['units']})"
    return f"Parameter {code}"
