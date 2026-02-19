"""Station registry for STOFS MCP server.

Hardcoded registry of the most important CO-OPS stations that appear in
STOFS model output. Used for quick lookups and filtering without requiring
a NetCDF download.
"""

from __future__ import annotations

import math

# ---------------------------------------------------------------------------
# Station registry (~50 key CO-OPS stations in STOFS output)
# ---------------------------------------------------------------------------

STOFS_STATIONS: list[dict] = [
    # US East Coast — Northeast
    {"id": "8410140", "name": "Eastport",           "state": "ME", "lat": 44.9038, "lon": -66.9822},
    {"id": "8419317", "name": "Wells",              "state": "ME", "lat": 43.3215, "lon": -70.5639},
    {"id": "8443970", "name": "Boston",             "state": "MA", "lat": 42.3539, "lon": -71.0503},
    {"id": "8449130", "name": "Nantucket",          "state": "MA", "lat": 41.2850, "lon": -70.0967},
    {"id": "8447930", "name": "Woods Hole",         "state": "MA", "lat": 41.5236, "lon": -70.6711},
    {"id": "8452660", "name": "Newport",            "state": "RI", "lat": 41.5043, "lon": -71.3261},
    {"id": "8461490", "name": "New London",         "state": "CT", "lat": 41.3614, "lon": -72.0900},
    {"id": "8516945", "name": "Kings Point",        "state": "NY", "lat": 40.8100, "lon": -73.7650},
    {"id": "8518750", "name": "The Battery",        "state": "NY", "lat": 40.7006, "lon": -74.0142},
    {"id": "8531680", "name": "Sandy Hook",         "state": "NJ", "lat": 40.4669, "lon": -74.0094},
    {"id": "8534720", "name": "Atlantic City",      "state": "NJ", "lat": 39.3550, "lon": -74.4183},
    {"id": "8557380", "name": "Lewes",              "state": "DE", "lat": 38.7817, "lon": -75.1194},
    {"id": "8570283", "name": "Ocean City Inlet",   "state": "MD", "lat": 38.3283, "lon": -75.0917},
    {"id": "8594900", "name": "Washington DC",      "state": "DC", "lat": 38.8733, "lon": -77.0217},
    {"id": "8638610", "name": "Sewells Point",      "state": "VA", "lat": 36.9467, "lon": -76.3300},
    # US East Coast — Mid-Atlantic / Southeast
    {"id": "8651370", "name": "Duck",               "state": "NC", "lat": 36.1833, "lon": -75.7467},
    {"id": "8656483", "name": "Beaufort",           "state": "NC", "lat": 34.7183, "lon": -76.6683},
    {"id": "8658120", "name": "Wilmington",         "state": "NC", "lat": 34.2275, "lon": -77.9536},
    {"id": "8665530", "name": "Charleston",         "state": "SC", "lat": 32.7817, "lon": -79.9250},
    {"id": "8670870", "name": "Fort Pulaski",       "state": "GA", "lat": 32.0367, "lon": -80.9017},
    {"id": "8720030", "name": "Fernandina Beach",   "state": "FL", "lat": 30.6717, "lon": -81.4650},
    {"id": "8720218", "name": "Mayport",            "state": "FL", "lat": 30.3967, "lon": -81.4300},
    {"id": "8721604", "name": "Trident Pier",       "state": "FL", "lat": 28.4150, "lon": -80.5933},
    {"id": "8722670", "name": "Lake Worth Pier",    "state": "FL", "lat": 26.6117, "lon": -80.0350},
    {"id": "8723214", "name": "Virginia Key",       "state": "FL", "lat": 25.7317, "lon": -80.1617},
    {"id": "8724580", "name": "Key West",           "state": "FL", "lat": 24.5508, "lon": -81.8075},
    {"id": "8725110", "name": "Naples",             "state": "FL", "lat": 26.1317, "lon": -81.8050},
    {"id": "8726520", "name": "St. Petersburg",     "state": "FL", "lat": 27.7606, "lon": -82.6269},
    # Gulf Coast
    {"id": "8729108", "name": "Panama City Beach",  "state": "FL", "lat": 30.2133, "lon": -85.8783},
    {"id": "8735180", "name": "Dauphin Island",     "state": "AL", "lat": 30.2500, "lon": -88.0750},
    {"id": "8741533", "name": "Bay Waveland YC",    "state": "MS", "lat": 30.3261, "lon": -89.3253},
    {"id": "8760721", "name": "Pilottown",          "state": "LA", "lat": 28.9317, "lon": -89.2567},
    {"id": "8761724", "name": "Grand Isle",         "state": "LA", "lat": 29.2633, "lon": -89.9567},
    {"id": "8768094", "name": "Calcasieu Pass",     "state": "LA", "lat": 29.7683, "lon": -93.3433},
    {"id": "8770570", "name": "Sabine Pass North",  "state": "TX", "lat": 29.7283, "lon": -93.8700},
    {"id": "8771013", "name": "Galveston Pier 21",  "state": "TX", "lat": 29.3100, "lon": -94.7933},
    {"id": "8771341", "name": "Galveston Bay Entr", "state": "TX", "lat": 29.3572, "lon": -94.7247},
    {"id": "8773037", "name": "Freeport",           "state": "TX", "lat": 28.9450, "lon": -95.3033},
    {"id": "8775870", "name": "Bob Hall Pier",      "state": "TX", "lat": 27.5800, "lon": -97.2167},
    {"id": "8779770", "name": "Port Isabel",        "state": "TX", "lat": 26.0617, "lon": -97.2150},
    # US West Coast
    {"id": "9410230", "name": "La Jolla",           "state": "CA", "lat": 32.8669, "lon": -117.2572},
    {"id": "9410840", "name": "Los Angeles",        "state": "CA", "lat": 33.7200, "lon": -118.2717},
    {"id": "9414290", "name": "San Francisco",      "state": "CA", "lat": 37.8063, "lon": -122.4659},
    {"id": "9418767", "name": "North Spit",         "state": "CA", "lat": 40.7667, "lon": -124.2167},
    {"id": "9431647", "name": "Port Orford",        "state": "OR", "lat": 42.7383, "lon": -124.4983},
    {"id": "9435380", "name": "South Beach",        "state": "OR", "lat": 44.6250, "lon": -124.0450},
    {"id": "9447130", "name": "Seattle",            "state": "WA", "lat": 47.6026, "lon": -122.3393},
    # Alaska
    {"id": "9457292", "name": "Cordova",            "state": "AK", "lat": 60.5583, "lon": -145.7533},
    {"id": "9468333", "name": "Unalakleet",         "state": "AK", "lat": 63.8717, "lon": -160.7933},
    # Hawaii
    {"id": "1611400", "name": "Nawiliwili",         "state": "HI", "lat": 21.9544, "lon": -159.3561},
    {"id": "1612340", "name": "Honolulu",           "state": "HI", "lat": 21.3067, "lon": -157.8650},
    # Territories
    {"id": "9751381", "name": "Lameshur Bay",       "state": "VI", "lat": 18.3183, "lon": -64.7233},
    {"id": "9755371", "name": "San Juan",           "state": "PR", "lat": 18.4597, "lon": -66.1164},
    {"id": "1631428", "name": "Pago Pago",          "state": "AS", "lat": -14.2767, "lon": -170.6900},
]

# ---------------------------------------------------------------------------
# Region bounding boxes for filtering
# ---------------------------------------------------------------------------

REGIONS: dict[str, dict] = {
    "east_coast": {"lat_min": 24.0, "lat_max": 47.0, "lon_min": -82.0, "lon_max": -65.0},
    "gulf":       {"lat_min": 24.0, "lat_max": 31.0, "lon_min": -98.0, "lon_max": -82.0},
    "west_coast": {"lat_min": 32.0, "lat_max": 49.0, "lon_min": -125.0, "lon_max": -117.0},
    "alaska":     {"lat_min": 51.0, "lat_max": 72.0, "lon_min": -180.0, "lon_max": -130.0},
    "hawaii":     {"lat_min": 18.0, "lat_max": 23.0, "lon_min": -161.0, "lon_max": -154.0},
    "puerto_rico":{"lat_min": 17.0, "lat_max": 19.0, "lon_min": -68.0,  "lon_max": -64.0},
}

# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

def get_station_by_id(station_id: str) -> dict | None:
    """Return station dict by CO-OPS ID, or None if not in registry."""
    for s in STOFS_STATIONS:
        if s["id"] == station_id:
            return s
    return None


def filter_by_region(stations: list[dict], region: str) -> list[dict]:
    """Filter stations to those within a named region bounding box."""
    bbox = REGIONS.get(region)
    if not bbox:
        return stations
    return [
        s for s in stations
        if bbox["lat_min"] <= s["lat"] <= bbox["lat_max"]
        and bbox["lon_min"] <= s["lon"] <= bbox["lon_max"]
    ]


def filter_by_state(stations: list[dict], state: str) -> list[dict]:
    """Filter stations by US state abbreviation (case-insensitive)."""
    state_upper = state.upper()
    return [s for s in stations if s["state"].upper() == state_upper]


def filter_by_proximity(
    stations: list[dict],
    lat: float,
    lon: float,
    radius_km: float,
) -> list[tuple[float, dict]]:
    """Return (distance_km, station) tuples for stations within radius_km."""
    results = []
    for s in stations:
        dist = _haversine(lat, lon, s["lat"], s["lon"])
        if dist <= radius_km:
            results.append((dist, s))
    results.sort(key=lambda x: x[0])
    return results


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in km."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
