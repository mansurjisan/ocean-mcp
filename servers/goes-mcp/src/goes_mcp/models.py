"""Constants and data models for GOES satellite imagery."""

# --- API Base URLs ---
STAR_CDN_BASE = "https://cdn.star.nesdis.noaa.gov"
SLIDER_BASE_URL = "https://slider.cira.colostate.edu"

# --- Satellites ---
SATELLITES: dict[str, dict] = {
    "goes-19": {
        "id": "GOES19",
        "name": "GOES-19 (East)",
        "position": "75.2°W",
        "description": "GOES-East — covers eastern US, Atlantic, Caribbean",
    },
    "goes-18": {
        "id": "GOES18",
        "name": "GOES-18 (West)",
        "position": "137.0°W",
        "description": "GOES-West — covers western US, Pacific, Alaska, Hawaii",
    },
}

# --- Coverages (CDN path segments) ---
COVERAGES: dict[str, dict] = {
    "CONUS": {
        "name": "Continental US",
        "description": "Continental United States view",
        "path": "CONUS",
    },
    "FD": {
        "name": "Full Disk",
        "description": "Full Earth disk view from geostationary orbit",
        "path": "FD",
    },
}

# --- Sectors (sub-regions under SECTOR/) ---
SECTORS: dict[str, dict] = {
    "se": {
        "name": "Southeast US",
        "description": "Southeastern United States including Gulf Coast",
        "path": "SECTOR/se",
    },
    "ne": {
        "name": "Northeast US",
        "description": "Northeastern United States including Mid-Atlantic",
        "path": "SECTOR/ne",
    },
    "car": {
        "name": "Caribbean",
        "description": "Caribbean Sea and surrounding islands",
        "path": "SECTOR/car",
    },
    "taw": {
        "name": "Tropical Atlantic Wide",
        "description": "Wide view of tropical Atlantic for hurricane tracking",
        "path": "SECTOR/taw",
    },
    "pr": {
        "name": "Puerto Rico",
        "description": "Puerto Rico and US Virgin Islands",
        "path": "SECTOR/pr",
    },
}

# --- ABI Bands ---
ABI_BANDS: dict[str, dict] = {
    "01": {
        "name": "Blue",
        "wavelength": "0.47 µm",
        "type": "Visible",
        "description": "Daytime aerosol, coastal water mapping",
    },
    "02": {
        "name": "Red",
        "wavelength": "0.64 µm",
        "type": "Visible",
        "description": "Daytime clouds, fog, wind fields",
    },
    "03": {
        "name": "Veggie",
        "wavelength": "0.86 µm",
        "type": "Near-IR",
        "description": "Vegetation, burn scars, aerosol",
    },
    "04": {
        "name": "Cirrus",
        "wavelength": "1.37 µm",
        "type": "Near-IR",
        "description": "Cirrus cloud detection",
    },
    "05": {
        "name": "Snow/Ice",
        "wavelength": "1.61 µm",
        "type": "Near-IR",
        "description": "Snow/ice discrimination, cloud phase",
    },
    "06": {
        "name": "Cloud Particle",
        "wavelength": "2.24 µm",
        "type": "Near-IR",
        "description": "Cloud particle size, vegetation, snow",
    },
    "07": {
        "name": "Shortwave IR",
        "wavelength": "3.9 µm",
        "type": "IR",
        "description": "Fire detection, fog, low clouds at night",
    },
    "08": {
        "name": "Upper Troposphere WV",
        "wavelength": "6.2 µm",
        "type": "IR",
        "description": "Upper-level water vapor, winds, jet stream",
    },
    "09": {
        "name": "Mid Troposphere WV",
        "wavelength": "6.9 µm",
        "type": "IR",
        "description": "Mid-level water vapor, winds",
    },
    "10": {
        "name": "Lower Troposphere WV",
        "wavelength": "7.3 µm",
        "type": "IR",
        "description": "Lower-level water vapor, winds, SO2",
    },
    "11": {
        "name": "Cloud-Top Phase",
        "wavelength": "8.4 µm",
        "type": "IR",
        "description": "Cloud-top phase, SO2, dust",
    },
    "12": {
        "name": "Ozone",
        "wavelength": "9.6 µm",
        "type": "IR",
        "description": "Total column ozone, turbulence",
    },
    "13": {
        "name": "Clean Longwave IR",
        "wavelength": "10.3 µm",
        "type": "IR",
        "description": "Cloud imagery, sea surface temperature",
    },
    "14": {
        "name": "Longwave IR",
        "wavelength": "11.2 µm",
        "type": "IR",
        "description": "Cloud imagery, sea surface temperature",
    },
    "15": {
        "name": "Dirty Longwave IR",
        "wavelength": "12.3 µm",
        "type": "IR",
        "description": "Cloud imagery, volcanic ash",
    },
    "16": {
        "name": "CO2 Longwave IR",
        "wavelength": "13.3 µm",
        "type": "IR",
        "description": "Cloud-top height, atmospheric temperature",
    },
}

# --- Composite Products ---
COMPOSITE_PRODUCTS: dict[str, dict] = {
    "GEOCOLOR": {
        "name": "GeoColor",
        "type": "Composite",
        "description": "True color (day) / IR + city lights (night) — best for general viewing",
    },
    "AirMass": {
        "name": "Air Mass",
        "type": "Composite",
        "description": "RGB composite showing air mass types and boundaries",
    },
    "Sandwich": {
        "name": "Sandwich",
        "type": "Composite",
        "description": "Visible imagery overlaid on infrared for cloud depth",
    },
    "FireTemperature": {
        "name": "Fire Temperature",
        "type": "Composite",
        "description": "Fire detection and temperature estimation",
    },
    "Dust": {
        "name": "Dust",
        "type": "Composite",
        "description": "Saharan and other dust plume detection",
    },
    "DMW": {
        "name": "Derived Motion Winds",
        "type": "Composite",
        "description": "Atmospheric motion vectors derived from sequential imagery",
    },
}

# All products (bands + composites)
PRODUCTS: dict[str, dict] = {**ABI_BANDS, **COMPOSITE_PRODUCTS}

# --- Resolutions ---
# STAR CDN resolution ladders are coverage-shaped, not one-size-fits-all:
# CONUS is a landscape ladder, while FD (Full Disk) and SECTOR imagery are
# each square at their own, different pixel sizes. Requesting a
# CONUS-shaped resolution against FD or SECTOR (or vice versa) 404s —
# verified live against cdn.star.nesdis.noaa.gov.
COMMON_RESOLUTIONS: dict[str, dict] = {
    "thumbnail": {
        "filename": "thumbnail.jpg",
        "pixels": "small preview (exact size varies by coverage)",
        "approx_size": "~40-130 KB",
    },
    "latest": {
        "filename": "latest.jpg",
        "pixels": "alias for this coverage's largest ladder resolution",
        "approx_size": "varies",
    },
}

CONUS_RESOLUTIONS: dict[str, dict] = {
    "625x375": {
        "filename": "625x375.jpg",
        "pixels": "625x375",
        "approx_size": "~270 KB",
    },
    "1250x750": {
        "filename": "1250x750.jpg",
        "pixels": "1250x750",
        "approx_size": "~900 KB",
    },
    "2500x1500": {
        "filename": "2500x1500.jpg",
        "pixels": "2500x1500",
        "approx_size": "~3 MB",
    },
    "5000x3000": {
        "filename": "5000x3000.jpg",
        "pixels": "5000x3000",
        "approx_size": "~9 MB",
    },
}

FD_RESOLUTIONS: dict[str, dict] = {
    "339x339": {
        "filename": "339x339.jpg",
        "pixels": "339x339",
        "approx_size": "~40 KB",
    },
    "678x678": {
        "filename": "678x678.jpg",
        "pixels": "678x678",
        "approx_size": "~150 KB",
    },
    "1808x1808": {
        "filename": "1808x1808.jpg",
        "pixels": "1808x1808",
        "approx_size": "~1 MB",
    },
    "5424x5424": {
        "filename": "5424x5424.jpg",
        "pixels": "5424x5424",
        "approx_size": "~8 MB",
    },
    "10848x10848": {
        "filename": "10848x10848.jpg",
        "pixels": "10848x10848",
        "approx_size": "~25 MB",
    },
}

SECTOR_RESOLUTIONS: dict[str, dict] = {
    "300x300": {
        "filename": "300x300.jpg",
        "pixels": "300x300",
        "approx_size": "~40 KB",
    },
    "600x600": {
        "filename": "600x600.jpg",
        "pixels": "600x600",
        "approx_size": "~150 KB",
    },
    "1200x1200": {
        "filename": "1200x1200.jpg",
        "pixels": "1200x1200",
        "approx_size": "~600 KB",
    },
    "2400x2400": {
        "filename": "2400x2400.jpg",
        "pixels": "2400x2400",
        "approx_size": "~2.5 MB",
    },
}

# Resolution ladder to validate against, keyed by coverage "kind": 'CONUS'
# and 'FD' are the two COVERAGES path segments; 'SECTOR' covers every
# regional sub-sector (all of which share the same square SECTOR/xx ladder).
RESOLUTIONS_BY_KIND: dict[str, dict[str, dict]] = {
    "CONUS": {**COMMON_RESOLUTIONS, **CONUS_RESOLUTIONS},
    "FD": {**COMMON_RESOLUTIONS, **FD_RESOLUTIONS},
    "SECTOR": {**COMMON_RESOLUTIONS, **SECTOR_RESOLUTIONS},
}

# Per-coverage-kind default resolution, used when a tool call doesn't
# specify one. CONUS keeps the historical 1250x750; FD and SECTOR get their
# own defaults since 1250x750 doesn't exist in either of their ladders.
DEFAULT_RESOLUTION_BY_KIND: dict[str, str] = {
    "CONUS": "1250x750",
    "FD": "1808x1808",
    "SECTOR": "1200x1200",
}

# Pixel dimensions to embed in a *timestamped* archive filename for the
# 'thumbnail'/'latest' aliases. The dated archive has no literal
# "..._thumbnail.jpg" or "..._latest.jpg" entry — only real WxH sizes — so
# these need resolving per coverage kind. (Only CONUS/FD are timestamped
# through STAR CDN's dated archive; SECTOR imagery is latest-only.)
TIMESTAMPED_THUMBNAIL_PIXELS: dict[str, str] = {
    "CONUS": "416x250",
    "FD": "339x339",
}
TIMESTAMPED_LATEST_PIXELS: dict[str, str] = {
    "CONUS": "5000x3000",
    "FD": "10848x10848",
}

# --- SLIDER coverage mapping ---
# SLIDER (slider.cira.colostate.edu) only publishes timestamps for the full
# CONUS and full-disk views (plus mesoscale_01/02, which this server doesn't
# expose) — none of our regional SECTOR/xx sub-sectors (se, ne, car, taw,
# pr) exist there; those are STAR-CDN-only. Verified live.
SLIDER_COVERAGES: dict[str, str] = {
    "CONUS": "conus",
    "FD": "full_disk",
}

# Maps our satellite keys to SLIDER satellite identifiers
SLIDER_SATELLITES: dict[str, str] = {
    "goes-19": "goes-19",
    "goes-18": "goes-18",
}

# Maps our product codes to SLIDER product identifiers
SLIDER_PRODUCTS: dict[str, str] = {
    "GEOCOLOR": "geocolor",
    "AirMass": "airmass",
    "Sandwich": "sandwich",
    "FireTemperature": "fire_temperature",
    "Dust": "dust",
    "DMW": "dmw",
    # Bands use zero-padded numbers
    **{f"{i:02d}": f"band_{i:02d}" for i in range(1, 17)},
}


def satellite_key_to_id(key: str) -> str:
    """Convert a user-friendly satellite key to CDN satellite ID.

    Args:
        key: Satellite key like 'goes-19' or 'goes-18'.

    Returns:
        CDN satellite ID like 'GOES19'.

    Raises:
        ValueError: If the key is not recognized.
    """
    key = key.lower().strip()
    if key not in SATELLITES:
        valid = ", ".join(sorted(SATELLITES.keys()))
        raise ValueError(f"Unknown satellite '{key}'. Valid options: {valid}")
    return SATELLITES[key]["id"]


def validate_product(product: str) -> str:
    """Validate and normalize a product code.

    Args:
        product: Product code (band number or composite name).

    Returns:
        Normalized product code.

    Raises:
        ValueError: If the product is not recognized.
    """
    # Try exact match first
    if product in PRODUCTS:
        return product
    # Try case-insensitive match for composites
    for key in PRODUCTS:
        if key.lower() == product.lower():
            return key
    valid_bands = ", ".join(sorted(ABI_BANDS.keys()))
    valid_composites = ", ".join(sorted(COMPOSITE_PRODUCTS.keys()))
    raise ValueError(
        f"Unknown product '{product}'. "
        f"Valid bands: {valid_bands}. "
        f"Valid composites: {valid_composites}"
    )


def validate_coverage(coverage: str) -> str:
    """Validate and return the CDN path for a coverage.

    Args:
        coverage: Coverage code like 'CONUS', 'FD'.

    Returns:
        CDN path segment.

    Raises:
        ValueError: If the coverage is not recognized.
    """
    upper = coverage.upper()
    if upper in COVERAGES:
        return COVERAGES[upper]["path"]
    valid = ", ".join(sorted(COVERAGES.keys()))
    raise ValueError(f"Unknown coverage '{coverage}'. Valid options: {valid}")


def validate_sector(sector: str) -> str:
    """Validate and return the CDN path for a sector.

    Args:
        sector: Sector code like 'se', 'ne', 'car'.

    Returns:
        CDN path segment like 'SECTOR/se'.

    Raises:
        ValueError: If the sector is not recognized.
    """
    lower = sector.lower().strip()
    if lower in SECTORS:
        return SECTORS[lower]["path"]
    valid = ", ".join(sorted(SECTORS.keys()))
    raise ValueError(f"Unknown sector '{sector}'. Valid options: {valid}")


def validate_resolution(resolution: str, kind: str) -> str:
    """Validate and return the filename for a resolution within a coverage kind.

    Resolutions are coverage-shaped (see RESOLUTIONS_BY_KIND) — a size valid
    for CONUS is not necessarily valid for FD or SECTOR, and vice versa.

    Args:
        resolution: Resolution key like '1250x750', 'thumbnail', 'latest'.
        kind: Which ladder to validate against — 'CONUS', 'FD', or 'SECTOR'.

    Returns:
        Filename like '1250x750.jpg'.

    Raises:
        ValueError: If the resolution is not valid for this coverage kind.
    """
    table = RESOLUTIONS_BY_KIND[kind]
    lower = resolution.lower().strip()
    if lower in table:
        return table[lower]["filename"]
    valid = ", ".join(sorted(table.keys()))
    raise ValueError(
        f"Unknown resolution '{resolution}' for {kind} coverage. "
        f"Valid options for {kind}: {valid}"
    )
