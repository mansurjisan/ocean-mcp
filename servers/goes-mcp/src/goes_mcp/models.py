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
RESOLUTIONS: dict[str, dict] = {
    "thumbnail": {
        "filename": "thumbnail.jpg",
        "pixels": "416x250",
        "approx_size": "~130 KB",
    },
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
    "latest": {
        "filename": "latest.jpg",
        "pixels": "5000x3000",
        "approx_size": "~9 MB (alias for 5000x3000)",
    },
}

# --- SLIDER sector mapping ---
# Maps our sector codes to SLIDER API sector identifiers
SLIDER_SECTORS: dict[str, str] = {
    "CONUS": "conus",
    "FD": "full_disk",
    "se": "southeast",
    "ne": "northeast",
    "car": "caribbean",
    "taw": "tropical_atlantic",
    "pr": "puerto_rico",
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


def validate_resolution(resolution: str) -> str:
    """Validate and return the filename for a resolution.

    Args:
        resolution: Resolution key like '1250x750', 'thumbnail', 'latest'.

    Returns:
        Filename like '1250x750.jpg'.

    Raises:
        ValueError: If the resolution is not recognized.
    """
    lower = resolution.lower().strip()
    if lower in RESOLUTIONS:
        return RESOLUTIONS[lower]["filename"]
    valid = ", ".join(sorted(RESOLUTIONS.keys()))
    raise ValueError(f"Unknown resolution '{resolution}'. Valid options: {valid}")
