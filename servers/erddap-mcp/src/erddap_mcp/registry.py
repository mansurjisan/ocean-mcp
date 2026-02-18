"""Known ERDDAP server registry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ERDDAPServer:
    """A known ERDDAP server."""

    name: str
    url: str
    focus: str
    region: str


# Well-known ERDDAP servers
SERVERS: list[ERDDAPServer] = [
    ERDDAPServer(
        name="CoastWatch West Coast",
        url="https://coastwatch.pfeg.noaa.gov/erddap",
        focus="Satellite, SST, chlorophyll",
        region="US West Coast",
    ),
    ERDDAPServer(
        name="CoastWatch CWHDF",
        url="https://cwcgom.aoml.noaa.gov/erddap",
        focus="Gulf of Mexico",
        region="Gulf of Mexico",
    ),
    ERDDAPServer(
        name="IOOS Gliders",
        url="https://gliders.ioos.us/erddap",
        focus="Underwater glider data",
        region="US National",
    ),
    ERDDAPServer(
        name="NCEI",
        url="https://www.ncei.noaa.gov/erddap",
        focus="Climate/archive data",
        region="Global",
    ),
    ERDDAPServer(
        name="OSMC",
        url="https://osmc.noaa.gov/erddap",
        focus="Observing system monitoring",
        region="Global",
    ),
    ERDDAPServer(
        name="NERACOOS",
        url="https://www.neracoos.org/erddap",
        focus="NE US regional ocean obs",
        region="US East Coast",
    ),
    ERDDAPServer(
        name="PacIOOS",
        url="https://pae-paha.pacioos.hawaii.edu/erddap",
        focus="Pacific Islands",
        region="Pacific",
    ),
    ERDDAPServer(
        name="BCO-DMO",
        url="https://erddap.bco-dmo.org/erddap",
        focus="Bio/chemical ocean data",
        region="Global",
    ),
    ERDDAPServer(
        name="NOAA UAF",
        url="https://upwell.pfeg.noaa.gov/erddap",
        focus="Fisheries, upwelling",
        region="US West Coast",
    ),
    ERDDAPServer(
        name="OOI",
        url="https://erddap.dataexplorer.oceanobservatories.org/erddap",
        focus="Ocean Observatories Initiative",
        region="US National",
    ),
    ERDDAPServer(
        name="SECOORA",
        url="https://erddap.secoora.org/erddap",
        focus="SE US regional ocean obs",
        region="US East Coast",
    ),
]

DEFAULT_SERVER_URL = "https://coastwatch.pfeg.noaa.gov/erddap"


def get_servers(
    region: str | None = None,
    keyword: str | None = None,
) -> list[ERDDAPServer]:
    """Filter and return matching ERDDAP servers.

    Args:
        region: Filter by region (case-insensitive substring match).
        keyword: Filter by keyword matching name, focus, or region.

    Returns:
        List of matching ERDDAPServer objects.
    """
    results = SERVERS

    if region:
        region_lower = region.lower()
        results = [s for s in results if region_lower in s.region.lower()]

    if keyword:
        keyword_lower = keyword.lower()
        results = [
            s
            for s in results
            if keyword_lower in s.name.lower()
            or keyword_lower in s.focus.lower()
            or keyword_lower in s.region.lower()
        ]

    return results
