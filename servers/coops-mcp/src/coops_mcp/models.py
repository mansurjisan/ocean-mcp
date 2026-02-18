"""Pydantic models for CO-OPS MCP server validation and response formatting."""

from enum import Enum


class Datum(str, Enum):
    MLLW = "MLLW"
    MHHW = "MHHW"
    MSL = "MSL"
    NAVD = "NAVD"
    STND = "STND"
    MHW = "MHW"
    MLW = "MLW"
    MTL = "MTL"
    IGLD = "IGLD"
    LWD = "LWD"


class Units(str, Enum):
    METRIC = "metric"
    ENGLISH = "english"


class TimeZone(str, Enum):
    GMT = "gmt"
    LST = "lst"
    LST_LDT = "lst_ldt"


class Interval(str, Enum):
    SIX_MIN = "6"
    HOURLY = "h"
    HILO = "hilo"


class DateShorthand(str, Enum):
    TODAY = "today"
    LATEST = "latest"
    RECENT = "recent"


class StationType(str, Enum):
    WATERLEVELS = "waterlevels"
    CURRENTPREDICTIONS = "currentpredictions"
    WATERLEVELSANDMET = "waterlevelsandmet"
    TCOON = "tcoon"
    NWLON = "nwlon"
    PORTS = "ports"


class MetProduct(str, Enum):
    WIND = "wind"
    AIR_TEMPERATURE = "air_temperature"
    WATER_TEMPERATURE = "water_temperature"
    AIR_PRESSURE = "air_pressure"
    HUMIDITY = "humidity"
    CONDUCTIVITY = "conductivity"
    SALINITY = "salinity"
    VISIBILITY = "visibility"
    AIR_GAP = "air_gap"


class CurrentsProduct(str, Enum):
    CURRENTS = "currents"
    CURRENTS_PREDICTIONS = "currents_predictions"
