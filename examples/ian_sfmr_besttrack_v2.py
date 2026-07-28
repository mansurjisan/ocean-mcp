"""SFMR-measured surface wind and HURDAT2 best track for Ian (2022) -- v2.

Same data and same content as ian_sfmr_vs_besttrack.py; this version is
re-exported at print resolution with all text at >= 14 pt for legibility in
the manuscript. The figure states the two measured quantities and leaves the
comparison to the caption.

Panel (a): SFMR radial wind profile, NOAA N42RF (P-3) mission of 2022-09-28,
from recon_get_sfmr.
Panel (b): HURDAT2 best-track intensity from nhc_get_best_track, with the
five landfall entries marked.

Inputs are saved MCP tool responses, so this replots without network access.
"""

import json
import os
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

DPI = int(os.environ.get("FIG_DPI", "200"))
OUTDIR = os.environ.get("FIG_OUT", "examples")

MS_PER_KT = 0.514444
LANDFALL_KT = 130  # HURDAT2, 2022-09-28 1905 UTC, Cayo Costa FL

SERIES_1 = "#2a78d6"  # blue   -- validated categorical slot 1
SERIES_2 = "#eb6834"  # orange -- validated categorical slot 2
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#d8d7d2"

# Every text element is >= 14 pt.
FS_TITLE = 20
FS_PANEL = 17
FS_LABEL = 16
FS_TICK = 14
FS_ANNOT = 15
FS_LEGEND = 15

# HURDAT2 flags landfall with record identifier 'L'. nhc_get_best_track parses
# that field but does not emit it, so these five landfall times come from the
# raw HURDAT2 file rather than from the tool response.
LANDFALLS = [
    ("2022-09-27 08:30", 110, "W Cuba"),
    ("2022-09-28 02:00", 110, "Dry Tortugas"),
    ("2022-09-28 19:05", 130, "Cayo Costa, FL"),
    ("2022-09-28 20:35", 125, "Pirate Harbor, FL"),
    ("2022-09-30 18:05", 70, "Georgetown, SC"),
]


def load():
    """Load the saved SFMR and best-track tool responses."""
    with open("examples/ian_sfmr_NOAA20220928H1.json") as fh:
        sfmr = json.load(fh)
    with open("examples/ian_besttrack_AL092022.json") as fh:
        track = json.load(fh)
    return sfmr, track


def parse_track_time(s):
    """Parse a best-track datetime string like '20220928 1905 UTC'."""
    return datetime.strptime(s.replace(" UTC", ""), "%Y%m%d %H%M")


def style(ax):
    """Recessive grid and axis styling with large ticks."""
    ax.grid(True, color=GRID, linewidth=0.8, alpha=0.9)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=FS_TICK)


def plot_radial_profile(ax, mission):
    """Draw SFMR mean and max surface wind against radius from storm center."""
    bins = mission["profile"]
    centers = [(b["radius_min_km"] + b["radius_max_km"]) / 2 for b in bins]
    mean_ws = [b["mean_wind_ms"] for b in bins]
    max_ws = [b["max_wind_ms"] for b in bins]

    ax.axhline(LANDFALL_KT * MS_PER_KT, color=MUTED, linewidth=1.8,
               linestyle=(0, (6, 4)), zorder=2)
    ax.annotate(
        f"HURDAT2 landfall intensity  {LANDFALL_KT} kt",
        xy=(204, LANDFALL_KT * MS_PER_KT), xytext=(0, -9),
        textcoords="offset points", ha="right", va="top",
        fontsize=FS_ANNOT, color=MUTED,
    )

    ax.plot(centers, max_ws, color=SERIES_2, linewidth=2.6, marker="o",
            markersize=6, markeredgecolor="white", markeredgewidth=0.9,
            label="Max wind", zorder=4)
    ax.plot(centers, mean_ws, color=SERIES_1, linewidth=2.6, marker="o",
            markersize=6, markeredgecolor="white", markeredgewidth=0.9,
            label="Mean wind", zorder=3)

    peak_r = centers[max_ws.index(max(max_ws))]
    peak_w = max(max_ws)
    ax.plot([peak_r], [peak_w], marker="o", markersize=13, color=SERIES_2,
            markeredgecolor="white", markeredgewidth=2.2, zorder=5)
    ax.annotate(
        f"{peak_w:.1f} m s$^{{-1}}$  ({peak_w / MS_PER_KT:.1f} kt)\n"
        f"{mission['peak_radius_km']} km radius",
        xy=(peak_r, peak_w), xytext=(36, 12), textcoords="offset points",
        fontsize=FS_ANNOT, color=INK,
        arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=1.3),
    )

    ax.set_xlabel("Radius from storm center (km)", fontsize=FS_LABEL, color=MUTED)
    ax.set_ylabel("SFMR surface wind (m s$^{-1}$)", fontsize=FS_LABEL, color=MUTED)
    ax.set_xlim(0, 210)
    ax.set_ylim(0, 82)

    # Secondary scale is the same measure in knots -- a unit conversion.
    kt_ax = ax.secondary_yaxis(
        "right", functions=(lambda v: v / MS_PER_KT, lambda v: v * MS_PER_KT)
    )
    kt_ax.set_ylabel("(kt)", fontsize=FS_LABEL, color=MUTED)
    kt_ax.tick_params(colors=MUTED, labelsize=FS_TICK)

    ax.set_title(
        f"(a)  SFMR radial wind profile\n{mission['aircraft']}, "
        f"{mission['n_obs']:,} observations",
        fontsize=FS_PANEL, color=INK, loc="left", pad=12,
    )
    ax.legend(frameon=False, fontsize=FS_LEGEND, loc="upper right", labelcolor=MUTED)


def plot_intensity(ax, track, mission_date):
    """Draw best-track intensity over time with landfalls marked."""
    pts = track["track_points"]
    times = [parse_track_time(p["datetime"]) for p in pts]
    winds = [p["max_wind"] for p in pts]

    day_start = datetime.strptime(mission_date, "%Y%m%d")
    day_end = day_start.replace(hour=23, minute=59)
    ax.axvspan(day_start, day_end, color=SERIES_1, alpha=0.09, zorder=1)
    ax.annotate(
        "SFMR mission\n2022-09-28", xy=(day_start, 6), xytext=(6, 0),
        textcoords="offset points", fontsize=FS_ANNOT, color=MUTED, va="bottom",
    )

    ax.plot(times, winds, color=SERIES_1, linewidth=2.6, zorder=3)

    lf_times = [datetime.strptime(t, "%Y-%m-%d %H:%M") for t, _, _ in LANDFALLS]
    lf_winds = [w for _, w, _ in LANDFALLS]
    ax.plot(lf_times, lf_winds, linestyle="none", marker="v", markersize=13,
            color=SERIES_2, markeredgecolor="white", markeredgewidth=1.4,
            label="Landfall (HURDAT2 'L')", zorder=5)

    lf_t = datetime.strptime("2022-09-28 19:05", "%Y-%m-%d %H:%M")
    ax.annotate(
        "Cayo Costa, FL\n2022-09-28 19:05 UTC\n130 kt / 941 mb",
        xy=(lf_t, LANDFALL_KT), xytext=(18, -72), textcoords="offset points",
        fontsize=FS_ANNOT, color=INK,
        arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=1.3),
    )

    ax.set_ylabel("Best-track max wind (kt)", fontsize=FS_LABEL, color=MUTED)
    ax.set_xlabel("2022 (UTC)", fontsize=FS_LABEL, color=MUTED)
    ax.set_ylim(0, 165)
    # Headroom on the right so the landfall annotation does not reach the edge.
    ax.set_xlim(datetime(2022, 9, 21), datetime(2022, 10, 4))
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.set_title(
        f"(b)  HURDAT2 best track\n{track['storm_id']}, {track['count']} track points",
        fontsize=FS_PANEL, color=INK, loc="left", pad=12,
    )
    ax.legend(frameon=False, fontsize=FS_LEGEND, loc="upper left", labelcolor=MUTED)


def main():
    sfmr, track = load()
    mission = sfmr["missions"][0]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(17, 7.6))
    plot_radial_profile(ax1, mission)
    plot_intensity(ax2, track, mission["date"])
    for ax in (ax1, ax2):
        style(ax)

    fig.suptitle(
        "Hurricane Ian (AL092022) - aircraft SFMR and HURDAT2 best track",
        fontsize=FS_TITLE, color=INK, x=0.005, ha="left", y=0.985,
    )
    fig.text(
        0.005, 0.012,
        "Sources: AOML HRD SFMR archive via recon_get_sfmr; NOAA HURDAT2 via "
        "nhc_get_best_track.\nLandfall times from the raw HURDAT2 record identifier 'L'.",
        fontsize=13, color=MUTED, ha="left", va="bottom",
    )
    fig.tight_layout(rect=(0, 0.07, 1, 0.955))

    out = os.path.join(OUTDIR, "ian_sfmr_besttrack_v2.png")
    fig.savefig(out, dpi=DPI, facecolor="white")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
