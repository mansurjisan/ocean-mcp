"""Observed water levels and tide residuals at two CO-OPS stations during Ian.

Top panel: observed 6-min water levels (MLLW) from coops_get_water_levels.
Bottom panel: residual = observed - harmonic prediction, from
coops_get_tide_predictions over the identical fixed window. The residual is
the non-tidal component -- the storm surge proper.

Fort Myers (8725520) reaches +2.209 m of positive residual; St. Petersburg
(8726520) reaches -1.755 m of negative residual (blowout) within 40 minutes
of it, on opposite sides of the Cayo Costa landfall.

Both inputs are saved MCP tool responses over the same fixed arguments
(begin_date=2022-09-27, end_date=2022-09-29, datum=MLLW, units=metric,
time_zone=gmt, interval=6), so this replots without network access.
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

SERIES_1 = "#2a78d6"  # blue   -- validated categorical slot 1
SERIES_2 = "#eb6834"  # orange -- validated categorical slot 2
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#d8d7d2"

LANDFALL = datetime(2022, 9, 28, 19, 5)  # HURDAT2 'L', Cayo Costa FL

OBS_FILE = "examples/ian_coops_water_levels.json"
PRED_FILE = "examples/ian_coops_tide_predictions.json"
STATIONS = [("8725520", SERIES_1), ("8726520", SERIES_2)]

# Every text element is >= 14 pt.
FS_TITLE = 20
FS_PANEL = 17
FS_LABEL = 16
FS_TICK = 14
FS_ANNOT = 15
FS_LEGEND = 15


def load_series():
    """Return {station: (name, times, observed, predicted, residual)}."""
    obs_all = json.load(open(OBS_FILE))
    pred_all = json.load(open(PRED_FILE))
    out = {}
    for station_id, _ in STATIONS:
        name = obs_all[station_id]["data"]["metadata"]["name"]
        obs = {
            r["t"]: float(r["v"])
            for r in obs_all[station_id]["data"]["data"]
            if r.get("v") not in (None, "", " ")
        }
        pred = {
            r["t"]: float(r["v"])
            for r in pred_all[station_id]["data"]["predictions"]
            if r.get("v") not in (None, "", " ")
        }
        stamps = sorted(set(obs) & set(pred))
        times = [datetime.strptime(t, "%Y-%m-%d %H:%M") for t in stamps]
        out[station_id] = (
            name,
            times,
            [obs[t] for t in stamps],
            [pred[t] for t in stamps],
            [round(obs[t] - pred[t], 4) for t in stamps],
        )
    return out


def style(ax):
    """Recessive grid, hidden top/right spines, large ticks."""
    ax.grid(True, color=GRID, linewidth=0.8, alpha=0.9)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=FS_TICK)


def mark_landfall(ax, label=False, y=None):
    """Draw the landfall line, optionally labelled."""
    ax.axvline(LANDFALL, color=INK, linewidth=1.6, linestyle=(0, (5, 4)), zorder=3)
    if label:
        ax.annotate(
            "Landfall\n2022-09-28 19:05 UTC\n130 kt / 941 mb",
            xy=(LANDFALL, y),
            xytext=(-10, 0),
            textcoords="offset points",
            ha="right",
            va="top",
            fontsize=FS_ANNOT,
            color=INK,
        )


def main():
    data = load_series()

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # ---- top: observed water levels -------------------------------------
    ax1.axhline(0, color=MUTED, linewidth=1.1, zorder=2)
    for station_id, color in STATIONS:
        name, times, obs, _, _ = data[station_id]
        ax1.plot(times, obs, color=color, linewidth=2.2,
                 label=f"{name} ({station_id})", zorder=4)
    mark_landfall(ax1, label=True, y=3.02)
    ax1.set_ylabel("Observed water level\n(m, MLLW)", fontsize=FS_LABEL, color=MUTED)
    ax1.set_ylim(-1.8, 3.1)
    ax1.set_title("(a)  Observed water levels", fontsize=FS_PANEL, color=INK,
                  loc="left", pad=10)
    ax1.legend(frameon=False, fontsize=FS_LEGEND, loc="lower left", labelcolor=MUTED)
    style(ax1)

    # ---- bottom: residual = observed - predicted ------------------------
    ax2.axhline(0, color=MUTED, linewidth=1.1, zorder=2)
    for station_id, color in STATIONS:
        name, times, _, _, resid = data[station_id]
        ax2.plot(times, resid, color=color, linewidth=2.2,
                 label=f"{name} ({station_id})", zorder=4)

        peak_i = max(range(len(resid)), key=lambda i: resid[i])
        min_i = min(range(len(resid)), key=lambda i: resid[i])
        idx = peak_i if abs(resid[peak_i]) > abs(resid[min_i]) else min_i
        val = resid[idx]
        ax2.plot([times[idx]], [val], marker="o", markersize=11, color=color,
                 markeredgecolor="white", markeredgewidth=2, zorder=6)
        offset = (18, 14) if val > 0 else (18, -26)
        ax2.annotate(
            f"{val:+.3f} m\n{times[idx]:%b %d %H:%M} UTC",
            xy=(times[idx], val),
            xytext=offset,
            textcoords="offset points",
            fontsize=FS_ANNOT,
            color=INK,
            arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=1.2),
        )

    mark_landfall(ax2)
    ax2.set_ylabel("Residual, observed - predicted\n(m)", fontsize=FS_LABEL, color=MUTED)
    ax2.set_xlabel("2022 (UTC)", fontsize=FS_LABEL, color=MUTED)
    ax2.set_ylim(-2.7, 2.7)
    ax2.set_title("(b)  Non-tidal residual (storm surge)", fontsize=FS_PANEL,
                  color=INK, loc="left", pad=10)
    ax2.legend(frameon=False, fontsize=FS_LEGEND, loc="lower left", labelcolor=MUTED)
    style(ax2)

    ax2.set_xlim(datetime(2022, 9, 27), datetime(2022, 9, 30))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=12))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))

    fig.suptitle(
        "Hurricane Ian (2022) - observed water levels and tide residuals",
        fontsize=FS_TITLE, color=INK, x=0.006, ha="left", y=0.985,
    )
    fig.text(
        0.006, 0.012,
        "Source: NOAA CO-OPS via coops_get_water_levels and coops_get_tide_predictions\n"
        "(2022-09-27 to 2022-09-29, datum MLLW, 6-min; 720 matched pairs per station; "
        "1983-2001 National Tidal Datum Epoch).",
        fontsize=13, color=MUTED, ha="left", va="bottom",
    )
    fig.tight_layout(rect=(0, 0.055, 1, 0.96))

    out = os.path.join(OUTDIR, "ian_water_levels_residuals.png")
    fig.savefig(out, dpi=DPI, facecolor="white")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
