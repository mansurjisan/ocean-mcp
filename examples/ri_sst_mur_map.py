"""MUR SST over Rhode Island / Block Island Sound, 2024-07-15.

Uses the SAME dataset, variable and literal timestamp as the manuscript's
point-extraction example (jplMURSST41, analysed_sst, 2024-07-15T09:00:00Z),
and overlays the extraction point 41.2 N, 71.6 W = 22.681 degree_C.

Data comes from the MCP tool erddap_get_griddap_data over a stdio session --
see fetch step in the report -- NOT from a direct ERDDAPClient import. The
saved response is examples/ri_sst_mur_20240715.json (17,061 grid points,
121 lat x 141 lon at 0.01 deg, untruncated with max_records=30000).
"""

import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import cartopy.crs as ccrs
import cartopy.feature as cfeature

DPI = int(os.environ.get("FIG_DPI", "200"))
OUTDIR = os.environ.get("FIG_OUT", "examples")
SRC = "examples/ri_sst_mur_20240715.json"

INK = "#0b0b0b"
MUTED = "#52514e"

# Point-extraction location and value from the manuscript example.
PT_LAT, PT_LON, PT_VAL = 41.2, -71.6, 22.681

FS_TITLE = 19
FS_LABEL = 16
FS_TICK = 14
FS_ANNOT = 15


def load_grid():
    """Reshape the tool's row-oriented JSON into a 2-D SST grid."""
    payload = json.load(open(SRC))
    rows = payload["data"]
    lats = sorted({r["latitude"] for r in rows})
    lons = sorted({r["longitude"] for r in rows})
    li = {v: i for i, v in enumerate(lats)}
    oi = {v: i for i, v in enumerate(lons)}
    grid = np.full((len(lats), len(lons)), np.nan)
    for r in rows:
        v = r.get("analysed_sst")
        if v is not None:
            grid[li[r["latitude"]], oi[r["longitude"]]] = v
    return payload, np.array(lats), np.array(lons), grid


def main():
    payload, lats, lons, grid = load_grid()

    fig, ax = plt.subplots(
        figsize=(13, 11), subplot_kw={"projection": ccrs.PlateCarree()}
    )
    ax.set_extent([-72.2, -70.8, 40.8, 42.0], crs=ccrs.PlateCarree())

    # Sequential single-hue ramp, light -> dark. No rainbow.
    mesh = ax.pcolormesh(
        lons, lats, grid, cmap="Reds", shading="nearest",
        transform=ccrs.PlateCarree(), zorder=2,
    )

    ax.add_feature(cfeature.LAND, facecolor="#ece7dd", edgecolor="none", zorder=3)
    ax.add_feature(cfeature.COASTLINE, linewidth=1.0, edgecolor="#4a4a48", zorder=4)
    ax.add_feature(cfeature.STATES, linewidth=0.6, edgecolor="#8a8a86", zorder=4)

    # Point-extraction marker
    ax.plot(PT_LON, PT_LAT, marker="o", markersize=15, color="#2a78d6",
            markeredgecolor="white", markeredgewidth=2.5,
            transform=ccrs.PlateCarree(), zorder=6)
    ax.annotate(
        f"Point extraction\n{PT_LAT} N, {abs(PT_LON)} W\n{PT_VAL} $\\degree$C",
        xy=(PT_LON, PT_LAT), xycoords=ccrs.PlateCarree()._as_mpl_transform(ax),
        xytext=(26, -30), textcoords="offset points",
        fontsize=FS_ANNOT, color=INK,
        bbox=dict(boxstyle="round,pad=0.45", facecolor="white",
                  edgecolor="#c9c8c3", alpha=0.92),
        arrowprops=dict(arrowstyle="-", color=INK, linewidth=1.4),
        zorder=7,
    )

    gl = ax.gridlines(draw_labels=True, linewidth=0.6, color="#d8d7d2", alpha=0.9)
    gl.top_labels = False
    gl.right_labels = False
    gl.xlabel_style = {"size": FS_TICK, "color": MUTED}
    gl.ylabel_style = {"size": FS_TICK, "color": MUTED}

    cbar = fig.colorbar(mesh, ax=ax, orientation="vertical", pad=0.02, shrink=0.82)
    cbar.set_label("Analysed sea surface temperature ($\\degree$C)",
                   fontsize=FS_LABEL, color=MUTED)
    cbar.ax.tick_params(labelsize=FS_TICK, colors=MUTED)

    ax.set_title(
        "MUR SST (jplMURSST41), 2024-07-15T09:00:00Z\n"
        "Rhode Island / Block Island Sound",
        fontsize=FS_TITLE, color=INK, loc="left", pad=12,
    )

    finite = np.isfinite(grid)
    fig.text(
        0.012, 0.015,
        "Source: NOAA CoastWatch ERDDAP via erddap_get_griddap_data\n"
        f"analysed_sst, 0.01 deg, stride 1; {payload['record_count']:,} grid points "
        f"({int(finite.sum()):,} over water), truncated={payload['truncated']}.",
        fontsize=12.5, color=MUTED, ha="left", va="bottom",
    )
    fig.tight_layout(rect=(0, 0.035, 1, 1))

    out = os.path.join(OUTDIR, "ri_sst_mur_20240715.png")
    fig.savefig(out, dpi=DPI, facecolor="white")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
