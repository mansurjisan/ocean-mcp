"""Enums and constants for NHC MCP server."""

from enum import Enum


class Basin(str, Enum):
    """NHC tropical cyclone basins."""

    AL = "al"  # Atlantic
    EP = "ep"  # East Pacific
    CP = "cp"  # Central Pacific


class StormClassification(str, Enum):
    """Tropical cyclone classification based on wind speed."""

    TD = "TD"  # Tropical Depression (< 34 kt)
    TS = "TS"  # Tropical Storm (34–63 kt)
    HU = "HU"  # Hurricane (64+ kt)
    SD = "SD"  # Subtropical Depression
    SS = "SS"  # Subtropical Storm
    EX = "EX"  # Extratropical
    LO = "LO"  # Low / remnant low
    DB = "DB"  # Disturbance
    WV = "WV"  # Tropical Wave


# Saffir-Simpson category thresholds (knots)
SAFFIR_SIMPSON = [
    (137, "Category 5"),
    (113, "Category 4"),
    (96, "Category 3"),
    (83, "Category 2"),
    (64, "Category 1"),
    (34, "Tropical Storm"),
    (0, "Tropical Depression"),
]


def classify_wind_speed(wind_kt: int) -> str:
    """Return Saffir-Simpson category string for a given wind speed in knots."""
    for threshold, label in SAFFIR_SIMPSON:
        if wind_kt >= threshold:
            return label
    return "Tropical Depression"
