"""Enums, constants, and data models for reconnaissance data."""

from __future__ import annotations

from enum import Enum


class Basin(str, Enum):
    """Tropical cyclone basins."""

    AL = "al"
    EP = "ep"
    CP = "cp"


class ReconProduct(str, Enum):
    """NHC reconnaissance archive product types."""

    HDOB = "hdob"
    VDM = "vdm"
    DROPSONDE = "dropsonde"


# WMO product directory codes on the NHC recon archive.
# Key: (product, basin) → directory name under /archive/recon/{YYYY}/
PRODUCT_DIRS: dict[tuple[str, str], str] = {
    ("hdob", "al"): "AHONT1",
    ("hdob", "ep"): "AHOPN1",
    ("vdm", "al"): "REPNT2",
    ("vdm", "ep"): "REPPN2",
    ("dropsonde", "al"): "REPNT3",
    ("dropsonde", "ep"): "REPPN3",
}

# Base URLs
NHC_RECON_ARCHIVE_BASE = "https://www.nhc.noaa.gov/archive/recon"
ATCF_FIX_BASE = "https://ftp.nhc.noaa.gov/atcf/fix"
