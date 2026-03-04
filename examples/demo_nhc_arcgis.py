"""
NHC MCP ArcGIS Layer Demo
=========================
Demonstrates the NHC MCP's ArcGIS integration:

  - Live mode:    Queries NHC ArcGIS MapServer for active storm forecast tracks
                  and watch/warning areas. Produces a map with forecast cone.

  - Fallback mode: If no storms are active (off-season), loads Hurricane Milton
                   (AL142024, Cat 5) from HURDAT2 and plots its best track.

Requires:
    pip install matplotlib cartopy

Run:
    python demo_nhc_arcgis.py
"""

import asyncio
import sys
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe

# Colour ramp for Saffir-Simpson categories
SS_COLORS = {
    "Tropical Depression": "#5ebaff",
    "Tropical Storm":      "#00faf4",
    "Category 1":          "#ffffcc",
    "Category 2":          "#ffe775",
    "Category 3":          "#ffc140",
    "Category 4":          "#ff8f20",
    "Category 5":          "#ff6060",
}

def classify(wind_kt):
    if wind_kt is None:
        return "Tropical Depression"
    if wind_kt >= 137: return "Category 5"
    if wind_kt >= 113: return "Category 4"
    if wind_kt >= 96:  return "Category 3"
    if wind_kt >= 83:  return "Category 2"
    if wind_kt >= 64:  return "Category 1"
    if wind_kt >= 34:  return "Tropical Storm"
    return "Tropical Depression"


async def get_active_forecast(client):
    """Try to get forecast track from ArcGIS for an active storm."""
    from nhc_mcp.utils import get_arcgis_layer_id

    storms = await client.get_active_storms()
    if not storms:
        return None, None

    storm = storms[0]
    bin_number = storm.get("binNumber", "AT1")
    storm_name = storm.get("name", "Unknown")

    layer_id = get_arcgis_layer_id(bin_number, "forecast_points")
    data = await client.query_arcgis_layer(layer_id)
    features = data.get("features", [])
    if not features:
        return None, None

    points = []
    for feat in features:
        attrs = feat.get("attributes", {})
        geom = feat.get("geometry", {})
        points.append({
            "tau":      attrs.get("tau", 0),
            "lat":      geom.get("y", attrs.get("lat")),
            "lon":      geom.get("x", attrs.get("lon")),
            "wind":     attrs.get("maxwind"),
            "label":    attrs.get("datelbl", ""),
            "type":     attrs.get("tcdvlp", ""),
        })
    points.sort(key=lambda p: int(p["tau"]) if str(p["tau"]).isdigit() else 0)
    return storm_name, points


async def get_hurdat2_track(client, storm_id="AL142024"):
    """Load a HURDAT2 best track as fallback."""
    from nhc_mcp.utils import parse_hurdat2

    text = await client.get_hurdat2("al")
    storms = parse_hurdat2(text)
    for s in storms:
        if s["id"] == storm_id:
            points = []
            for pt in s["track"]:
                if pt["lat"] is None:
                    continue
                points.append({
                    "tau":   None,
                    "lat":   pt["lat"],
                    "lon":   pt["lon"],
                    "wind":  pt["max_wind"],
                    "label": f"{pt['date'][4:6]}/{pt['date'][6:8]} {pt['time']}Z",
                    "type":  pt["status"],
                })
            return s["name"], points
    return None, None


def plot_track(storm_name, points, source_label):
    """Plot the hurricane track coloured by Saffir-Simpson category."""
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
        proj = ccrs.PlateCarree()
        use_cartopy = True
    except ImportError:
        use_cartopy = False

    lats = [p["lat"] for p in points if p["lat"] is not None]
    lons = [p["lon"] for p in points if p["lon"] is not None]
    if not lats:
        print("No valid coordinates to plot.")
        return

    lon_min, lon_max = min(lons) - 5, max(lons) + 5
    lat_min, lat_max = min(lats) - 5, max(lats) + 5

    fig = plt.figure(figsize=(14, 8))

    if use_cartopy:
        ax = fig.add_subplot(1, 1, 1, projection=proj)
        ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=proj)
        ax.add_feature(cfeature.LAND, facecolor="#e8e8e8", zorder=0)
        ax.add_feature(cfeature.OCEAN, facecolor="#cce5f0", zorder=0)
        ax.add_feature(cfeature.COASTLINE, linewidth=0.7, zorder=1)
        ax.add_feature(cfeature.BORDERS, linewidth=0.4, zorder=1)
        ax.add_feature(cfeature.STATES, linewidth=0.3, zorder=1)
        transform = proj
    else:
        ax = fig.add_subplot(1, 1, 1)
        ax.set_xlim(lon_min, lon_max)
        ax.set_ylim(lat_min, lat_max)
        ax.set_facecolor("#cce5f0")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        transform = None

    # Draw track segments coloured by category
    for i in range(len(points) - 1):
        p0, p1 = points[i], points[i + 1]
        if None in (p0["lat"], p0["lon"], p1["lat"], p1["lon"]):
            continue
        cat = classify(p0["wind"])
        color = SS_COLORS[cat]
        kwargs = dict(color=color, linewidth=3, zorder=2, solid_capstyle="round")
        if transform:
            ax.plot([p0["lon"], p1["lon"]], [p0["lat"], p1["lat"]],
                    transform=transform, **kwargs)
        else:
            ax.plot([p0["lon"], p1["lon"]], [p0["lat"], p1["lat"]], **kwargs)

    # Draw dots at each track point
    for p in points:
        if None in (p["lat"], p["lon"]):
            continue
        cat = classify(p["wind"])
        color = SS_COLORS[cat]
        kwargs = dict(color=color, markersize=8, markeredgecolor="black",
                      markeredgewidth=0.5, zorder=3)
        if transform:
            ax.plot(p["lon"], p["lat"], "o", transform=transform, **kwargs)
        else:
            ax.plot(p["lon"], p["lat"], "o", **kwargs)

    # Label every 4th point
    for i, p in enumerate(points):
        if i % 4 != 0 or None in (p["lat"], p["lon"]):
            continue
        label = p["label"] or ""
        txt_kwargs = dict(fontsize=7, zorder=4,
                          path_effects=[pe.withStroke(linewidth=2, foreground="white")])
        if transform:
            ax.text(p["lon"] + 0.4, p["lat"] + 0.4, label,
                    transform=transform, **txt_kwargs)
        else:
            ax.text(p["lon"] + 0.4, p["lat"] + 0.4, label, **txt_kwargs)

    # Legend
    legend_handles = [
        mpatches.Patch(color=SS_COLORS[cat], label=cat)
        for cat in SS_COLORS
    ]
    ax.legend(handles=legend_handles, loc="lower left", fontsize=8,
              title="Category", framealpha=0.9)

    peak_wind = max((p["wind"] for p in points if p["wind"]), default=0)
    peak_cat = classify(peak_wind)

    fig.suptitle(
        f"Hurricane {storm_name}  —  {source_label}\n"
        f"Peak intensity: {peak_wind} kt ({peak_cat})  |  {len(points)} track points",
        fontsize=13, fontweight="bold"
    )
    plt.tight_layout()
    out = f"nhc_track_{storm_name.lower()}.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"\nSaved → {out}")
    plt.show()


async def main():
    from nhc_mcp.client import NHCClient

    client = NHCClient()
    try:
        print("Checking for active storms via NHC ArcGIS MapServer...")
        storm_name, points = await get_active_forecast(client)

        if storm_name and points:
            source = f"NHC 5-Day Forecast Track (ArcGIS) — {datetime.utcnow():%Y-%m-%d %H:%M} UTC"
            print(f"Active storm: {storm_name} — {len(points)} forecast points")
        else:
            print("No active storms. Loading Hurricane Milton (AL142024) from HURDAT2...")
            storm_name, points = await get_hurdat2_track(client, "AL142024")
            source = "HURDAT2 Best Track Archive — AL142024"
            print(f"Loaded: {storm_name} — {len(points)} track points")

        print("\nTrack summary:")
        for p in points:
            cat = classify(p["wind"])
            tau_label = f"tau={p['tau']:3d}h  " if p["tau"] is not None else ""
            print(f"  {tau_label}{p['label']:20s}  {p['lat']:6.1f}N  {abs(p['lon']):6.1f}W  "
                  f"{str(p['wind']) + ' kt':8s}  {cat}")

        plot_track(storm_name, points, source)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
