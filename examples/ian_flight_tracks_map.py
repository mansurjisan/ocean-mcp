"""Plot SFMR flight tracks for Hurricane Ian (2022) with best track overlay."""

import asyncio
import sys

sys.path.insert(0, "servers/recon-mcp/src")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.patheffects as pe
import numpy as np

from recon_mcp.client import ReconClient
from recon_mcp.utils import (
    cleanup_temp_file,
    parse_atcf_best_track,
    parse_directory_listing,
    parse_sfmr_netcdf,
)
from recon_mcp.tools.sfmr import _decode_sfmr_filename


async def fetch_data():
    """Download best track and SFMR flight data."""
    client = ReconClient()
    try:
        # Fetch best track
        print("Fetching best track for AL092022...")
        bdeck_text = await client.fetch_best_track("al", 9, 2022)
        track = parse_atcf_best_track(bdeck_text)
        print(f"  {len(track)} track points")

        # List SFMR files
        sfmr_url = client.build_sfmr_url(2022, "ian")
        html = await client.list_directory(sfmr_url)
        entries = parse_directory_listing(html)
        nc_files = [e for e in entries if e["filename"].endswith(".nc")]
        print(f"  {len(nc_files)} SFMR files found")

        flights = []
        for entry in nc_files[:10]:
            fname = entry["filename"]
            file_url = sfmr_url + fname
            tmp_path = None
            try:
                print(f"  Downloading {fname}...")
                tmp_path = await client.download_netcdf(file_url)
                sfmr_data = parse_sfmr_netcdf(tmp_path)
                info = _decode_sfmr_filename(fname)

                # Filter out NaN positions
                mask = ~(np.isnan(sfmr_data["lat"]) | np.isnan(sfmr_data["lon"]))
                lats = sfmr_data["lat"][mask]
                lons = sfmr_data["lon"][mask]
                sws = sfmr_data["sws"][mask]

                if len(lats) > 0:
                    date_str = info.get("date", "")
                    if date_str and len(date_str) == 8:
                        label = f"Sep {date_str[6:]} #{info.get('mission_seq', '')}"
                    else:
                        label = fname

                    flights.append({
                        "label": label,
                        "date": date_str,
                        "lat": lats,
                        "lon": lons,
                        "sws": sws,
                        "filename": fname,
                    })
            except Exception as e:
                print(f"    Error: {e}")
            finally:
                cleanup_temp_file(tmp_path)

        return track, flights
    finally:
        await client.close()


def saffir_simpson_color(wind_kt):
    """Return color based on Saffir-Simpson category (wind in knots)."""
    if wind_kt < 34:
        return "#5B9BD5"   # TD - blue
    elif wind_kt < 64:
        return "#00B050"   # TS - green
    elif wind_kt < 83:
        return "#FFC000"   # Cat 1 - yellow
    elif wind_kt < 96:
        return "#FF8C00"   # Cat 2 - orange
    elif wind_kt < 113:
        return "#FF0000"   # Cat 3 - red
    elif wind_kt < 137:
        return "#C00000"   # Cat 4 - dark red
    else:
        return "#800080"   # Cat 5 - purple


def plot_map(track, flights):
    """Create the flight tracks map with best track overlay."""
    fig, ax = plt.subplots(figsize=(14, 10))

    # --- Flight tracks colored by SFMR surface wind speed ---
    # Use a consistent colormap for wind speed across all flights
    vmin, vmax = 0, 55  # m/s range
    cmap = plt.cm.YlOrRd

    # Sort flights by date so later (stronger) flights plot on top
    flights.sort(key=lambda f: f["date"])
    colors_flight = cm.tab10(np.linspace(0, 1, len(flights)))

    for i, flight in enumerate(flights):
        # Subsample for performance (every 30th point = ~30s intervals)
        step = 30
        lats = flight["lat"][::step]
        lons = flight["lon"][::step]
        sws = flight["sws"][::step]

        sc = ax.scatter(lons, lats, c=sws, cmap=cmap, vmin=vmin, vmax=vmax,
                        s=1.5, alpha=0.6, zorder=2)

    # Colorbar for SFMR winds
    cbar = plt.colorbar(sc, ax=ax, shrink=0.7, pad=0.02, aspect=30)
    cbar.set_label("SFMR Surface Wind Speed (m/s)", fontsize=11)
    # Add category markers on colorbar
    for thresh, cat in [(17, "TS"), (33, "Cat1"), (43, "Cat2"), (50, "Cat3")]:
        cbar.ax.axhline(y=thresh, color="black", linewidth=0.5, alpha=0.5)
        cbar.ax.text(1.5, thresh, cat, fontsize=7, va="center", transform=cbar.ax.get_yaxis_transform())

    # --- Best track overlay ---
    track_lats = [p["lat"] for p in track]
    track_lons = [p["lon"] for p in track]
    track_winds = [p["max_wind_kt"] or 0 for p in track]

    # Draw track line
    ax.plot(track_lons, track_lats, color="black", linewidth=1.5, alpha=0.7,
            zorder=5, label="Best Track")

    # Plot track points colored by Saffir-Simpson category
    for j, pt in enumerate(track):
        wind = pt["max_wind_kt"] or 0
        color = saffir_simpson_color(wind)
        ax.scatter(pt["lon"], pt["lat"], c=color, s=30, edgecolors="black",
                   linewidth=0.5, zorder=6)

    # Label select track points with date/time
    label_indices = list(range(0, len(track), 8))  # Every 2 days roughly
    if (len(track) - 1) not in label_indices:
        label_indices.append(len(track) - 1)

    for j in label_indices:
        pt = track[j]
        dt = pt["datetime"]
        wind = pt["max_wind_kt"] or 0
        label_text = f"{dt.strftime('%m/%d %HZ')}\n{wind} kt"
        ax.annotate(label_text, (pt["lon"], pt["lat"]),
                    textcoords="offset points", xytext=(10, 8),
                    fontsize=7, fontweight="bold",
                    path_effects=[pe.withStroke(linewidth=2, foreground="white")],
                    zorder=7)

    # --- Landmass outline (simple lat/lon grid) ---
    ax.set_facecolor("#E8F4FD")

    # Set map extent to cover Ian's track + flight area
    all_lats = track_lats.copy()
    all_lons = track_lons.copy()
    for f in flights:
        all_lats.extend(f["lat"][::100].tolist())
        all_lons.extend(f["lon"][::100].tolist())

    lat_margin = 2
    lon_margin = 2
    ax.set_xlim(min(all_lons) - lon_margin, max(all_lons) + lon_margin)
    ax.set_ylim(min(all_lats) - lat_margin, max(all_lats) + lat_margin)

    # Grid
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.set_xlabel("Longitude", fontsize=12)
    ax.set_ylabel("Latitude", fontsize=12)

    # --- Legend for Saffir-Simpson categories ---
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#5B9BD5",
               markersize=8, markeredgecolor="k", markeredgewidth=0.5, label="TD (<34 kt)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#00B050",
               markersize=8, markeredgecolor="k", markeredgewidth=0.5, label="TS (34-63 kt)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#FFC000",
               markersize=8, markeredgecolor="k", markeredgewidth=0.5, label="Cat 1 (64-82 kt)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#FF8C00",
               markersize=8, markeredgecolor="k", markeredgewidth=0.5, label="Cat 2 (83-95 kt)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#FF0000",
               markersize=8, markeredgecolor="k", markeredgewidth=0.5, label="Cat 3 (96-112 kt)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#C00000",
               markersize=8, markeredgecolor="k", markeredgewidth=0.5, label="Cat 4 (113-136 kt)"),
        Line2D([0], [0], color="black", linewidth=1.5, label="Best Track"),
    ]
    ax.legend(handles=legend_elements, loc="lower left", fontsize=8,
              title="Best Track (Saffir-Simpson)", title_fontsize=9,
              framealpha=0.9)

    # Title
    ax.set_title(
        "Hurricane Ian (2022) — SFMR Reconnaissance Flight Tracks\n"
        "Flight paths colored by surface wind speed, best track with Saffir-Simpson categories",
        fontsize=13, fontweight="bold"
    )

    plt.tight_layout()
    outpath = "ian_flight_tracks_map.png"
    plt.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"\nSaved: {outpath}")
    plt.close()


if __name__ == "__main__":
    track, flights = asyncio.run(fetch_data())
    print(f"\n{len(flights)} flights with valid data")
    plot_map(track, flights)
