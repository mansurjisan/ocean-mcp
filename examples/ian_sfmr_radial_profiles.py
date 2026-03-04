"""Plot SFMR radial wind profiles for Hurricane Ian (2022) reconnaissance missions."""

import asyncio
import sys

sys.path.insert(0, "servers/recon-mcp/src")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import numpy as np

from recon_mcp.client import ReconClient
from recon_mcp.utils import (
    cleanup_temp_file,
    compute_radial_wind_profile,
    parse_atcf_best_track,
    parse_directory_listing,
    parse_sfmr_netcdf,
)
from recon_mcp.tools.sfmr import _decode_sfmr_filename


async def fetch_all_profiles():
    """Download SFMR files and compute radial wind profiles."""
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

        missions = []
        for entry in nc_files[:10]:
            fname = entry["filename"]
            file_url = sfmr_url + fname
            tmp_path = None
            try:
                print(f"  Downloading {fname}...")
                tmp_path = await client.download_netcdf(file_url)
                sfmr_data = parse_sfmr_netcdf(tmp_path)
                profile = compute_radial_wind_profile(
                    sfmr_data, track, bin_size_km=5.0, max_radius_km=200.0
                )
                info = _decode_sfmr_filename(fname)

                if profile:
                    # Extract radius midpoints and wind values
                    radii = [(b["radius_min_km"] + b["radius_max_km"]) / 2 for b in profile]
                    mean_winds = [b["mean_wind_ms"] for b in profile]
                    max_winds = [b["max_wind_ms"] for b in profile]

                    date_str = info.get("date", "")
                    if date_str and len(date_str) == 8:
                        label = f"{date_str[4:6]}/{date_str[6:]} #{info.get('mission_seq', '')}"
                    else:
                        label = fname

                    missions.append({
                        "label": label,
                        "date": date_str,
                        "radii": radii,
                        "mean_winds": mean_winds,
                        "max_winds": max_winds,
                        "peak_wind": max(max_winds),
                        "filename": fname,
                    })
            except Exception as e:
                print(f"    Error: {e}")
            finally:
                cleanup_temp_file(tmp_path)

        return missions
    finally:
        await client.close()


def plot_profiles(missions):
    """Create the radial wind profile plot."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))

    # Sort by date for consistent coloring
    missions.sort(key=lambda m: m["date"])

    # Color map: cool colors for early, warm for later (intensification)
    colors = cm.plasma(np.linspace(0.1, 0.9, len(missions)))

    # Left panel: Mean wind profiles
    for i, m in enumerate(missions):
        ax1.plot(m["radii"], m["mean_winds"], color=colors[i], linewidth=1.8,
                 label=m["label"], alpha=0.85)

    ax1.set_xlabel("Radius from Storm Center (km)", fontsize=12)
    ax1.set_ylabel("Mean Surface Wind Speed (m/s)", fontsize=12)
    ax1.set_title("Mean SFMR Surface Wind", fontsize=13, fontweight="bold")
    ax1.legend(fontsize=9, title="Date  Mission", title_fontsize=9,
               loc="upper right", framealpha=0.9)
    ax1.set_xlim(0, 200)
    ax1.set_ylim(0, None)
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=33, color="red", linestyle="--", alpha=0.4, linewidth=0.8)
    ax1.text(195, 33.5, "Cat 1", fontsize=8, color="red", alpha=0.5, ha="right")

    # Right panel: Max wind profiles
    for i, m in enumerate(missions):
        ax2.plot(m["radii"], m["max_winds"], color=colors[i], linewidth=1.8,
                 label=m["label"], alpha=0.85)

    ax2.set_xlabel("Radius from Storm Center (km)", fontsize=12)
    ax2.set_ylabel("Max Surface Wind Speed (m/s)", fontsize=12)
    ax2.set_title("Max SFMR Surface Wind", fontsize=13, fontweight="bold")
    ax2.legend(fontsize=9, title="Date  Mission", title_fontsize=9,
               loc="upper right", framealpha=0.9)
    ax2.set_xlim(0, 200)
    ax2.set_ylim(0, None)
    ax2.grid(True, alpha=0.3)

    # Category thresholds on max wind panel
    for thresh, cat_label in [(33, "Cat 1"), (43, "Cat 2"), (50, "Cat 3")]:
        ax2.axhline(y=thresh, color="red", linestyle="--", alpha=0.3, linewidth=0.8)
        ax2.text(195, thresh + 0.5, cat_label, fontsize=8, color="red", alpha=0.5, ha="right")

    fig.suptitle("Hurricane Ian (2022) — SFMR Radial Wind Profiles\n"
                 "Surface wind speed vs. distance from storm center across recon missions",
                 fontsize=14, fontweight="bold", y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.93])

    outpath = "ian_sfmr_radial_profiles.png"
    plt.savefig(outpath, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"\nSaved: {outpath}")
    plt.close()


if __name__ == "__main__":
    missions = asyncio.run(fetch_all_profiles())
    print(f"\n{len(missions)} missions with valid profiles")
    plot_profiles(missions)
