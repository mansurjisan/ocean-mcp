"""Generate SST map for Rhode Island coast using ERDDAP data."""

import asyncio
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# Add the erddap-mcp source to path
import sys
sys.path.insert(0, "/mnt/d/ocean-mcp/servers/erddap-mcp/src")

from erddap_mcp.client import ERDDAPClient
from erddap_mcp.utils import parse_erddap_json

COASTWATCH_URL = "https://coastwatch.pfeg.noaa.gov/erddap"


async def fetch_sst():
    """Fetch SST data from ERDDAP for Rhode Island coast."""
    client = ERDDAPClient()
    try:
        # Use the blended SST product - wider area for context
        query = "analysed_sst[(last)][(40.8):(42.0)][(-72.2):(-70.8)]"
        data = await client.get_griddap(COASTWATCH_URL, "nesdisBLENDEDsstDNDaily", query)
        rows = parse_erddap_json(data)

        # Get the time from first row
        time_str = rows[0]["time"] if rows else "unknown"

        return rows, time_str
    finally:
        await client.close()


def make_map(rows, time_str):
    """Create SST map from ERDDAP data."""
    # Extract unique lats, lons, and build SST grid
    lats = sorted(set(r["latitude"] for r in rows))
    lons = sorted(set(r["longitude"] for r in rows))

    sst_grid = np.full((len(lats), len(lons)), np.nan)
    lat_idx = {lat: i for i, lat in enumerate(lats)}
    lon_idx = {lon: i for i, lon in enumerate(lons)}

    for r in rows:
        val = r["analysed_sst"]
        if val is not None:
            sst_grid[lat_idx[r["latitude"]], lon_idx[r["longitude"]]] = val

    lon_arr = np.array(lons)
    lat_arr = np.array(lats)

    # Create figure with cartopy
    fig, ax = plt.subplots(
        figsize=(10, 9),
        subplot_kw={"projection": ccrs.PlateCarree()},
    )

    # Set extent: [lon_min, lon_max, lat_min, lat_max]
    ax.set_extent([-72.2, -70.8, 40.8, 42.0], crs=ccrs.PlateCarree())

    # Add map features
    ax.add_feature(cfeature.LAND, facecolor="#f0e6d2", edgecolor="black", linewidth=0.5)
    ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
    ax.add_feature(cfeature.STATES, linewidth=0.5, edgecolor="gray")
    ax.add_feature(cfeature.BORDERS, linewidth=0.5)

    # Plot SST
    cmap = plt.cm.RdYlBu_r
    norm = mcolors.Normalize(vmin=0, vmax=5)

    mesh = ax.pcolormesh(
        lon_arr, lat_arr, sst_grid,
        cmap=cmap, norm=norm,
        transform=ccrs.PlateCarree(),
        shading="nearest",
    )

    # Colorbar
    cbar = plt.colorbar(mesh, ax=ax, shrink=0.7, pad=0.02)
    cbar.set_label("Sea Surface Temperature (\u00b0C)", fontsize=12)

    # Labels for key locations
    locations = {
        "Providence": (-71.41, 41.82),
        "Newport": (-71.31, 41.49),
        "Block Island": (-71.58, 41.17),
        "Point Judith": (-71.48, 41.36),
        "Narragansett Bay": (-71.38, 41.60),
        "Martha's Vineyard": (-70.60, 41.40),
        "Buzzards Bay": (-70.88, 41.63),
    }

    for name, (lon, lat) in locations.items():
        ax.plot(lon, lat, "ko", markersize=3, transform=ccrs.PlateCarree())
        ax.text(
            lon + 0.03, lat + 0.02, name,
            fontsize=7, fontweight="bold",
            transform=ccrs.PlateCarree(),
            bbox=dict(boxstyle="round,pad=0.15", facecolor="white", alpha=0.7, edgecolor="none"),
        )

    # Gridlines
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="gray", alpha=0.5)
    gl.top_labels = False
    gl.right_labels = False

    # Title
    date_display = time_str[:10] if len(time_str) >= 10 else time_str
    ax.set_title(
        f"Sea Surface Temperature — Rhode Island Coast\n"
        f"NOAA Geo-polar Blended SST | {date_display}",
        fontsize=13, fontweight="bold",
    )

    plt.tight_layout()
    outpath = "/mnt/d/ocean-mcp/ri_sst_map.png"
    fig.savefig(outpath, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {outpath}")
    return outpath


async def main():
    rows, time_str = await fetch_sst()
    print(f"Fetched {len(rows)} grid points, time: {time_str}")
    ocean_rows = [r for r in rows if r["analysed_sst"] is not None]
    vals = [r["analysed_sst"] for r in ocean_rows]
    print(f"Ocean points: {len(ocean_rows)}, SST range: {min(vals):.1f} - {max(vals):.1f} °C")
    make_map(rows, time_str)


asyncio.run(main())
