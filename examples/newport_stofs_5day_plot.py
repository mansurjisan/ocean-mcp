"""
Plot STOFS-2D-Global vs STOFS-3D-Atlantic water elevation forecast at Newport, RI,
overlaid with CO-OPS observed water levels using datum-matched observations.
Station 8452660 | Cycle: 2026-02-21 12z
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import json
from datetime import datetime

# --- Load forecast data ---
with open("/mnt/d/ocean-mcp/stofs_2d_newport.json") as f:
    d2 = json.load(f)
with open("/mnt/d/ocean-mcp/stofs_3d_newport.json") as f:
    d3 = json.load(f)

# --- Load datum-matched observations ---
with open("/mnt/d/ocean-mcp/coops_obs_newport.json") as f:
    obs_msl = json.load(f)       # MSL datum — matches STOFS-2D-Global (LMSL)
with open("/mnt/d/ocean-mcp/coops_obs_newport_navd88.json") as f:
    obs_navd = json.load(f)      # NAVD88 datum — matches STOFS-3D-Atlantic

# Parse times
times_2d = [datetime.strptime(t, "%Y-%m-%d %H:%M") for t in d2["times"]]
times_3d = [datetime.strptime(t, "%Y-%m-%d %H:%M") for t in d3["times"]]
times_obs_msl = [datetime.strptime(t, "%Y-%m-%d %H:%M") for t in obs_msl["times"]]
times_obs_navd = [datetime.strptime(t, "%Y-%m-%d %H:%M") for t in obs_navd["times"]]

# --- Two-panel plot: one per model with its matching obs ---
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

# Top panel: STOFS-2D-Global vs Obs (MSL)
ax1.plot(times_obs_msl, obs_msl["values"], color="black", linewidth=1.5, alpha=0.85,
         label=f"CO-OPS Observed (MSL)", zorder=3)
ax1.plot(times_2d, d2["values"], color="#2196F3", linewidth=1.0, alpha=0.85,
         label=f"STOFS-2D-Global (LMSL)", zorder=2)
ax1.axhline(y=0, color="gray", linewidth=0.5, linestyle="--", alpha=0.5)
ax1.set_ylabel("Water Elevation (m)")
ax1.set_title("STOFS-2D-Global vs Observations — MSL Datum", fontsize=11)
ax1.legend(loc="upper right", fontsize=9)
ax1.grid(True, alpha=0.3)

# Bottom panel: STOFS-3D-Atlantic vs Obs (NAVD88)
ax2.plot(times_obs_navd, obs_navd["values"], color="black", linewidth=1.5, alpha=0.85,
         label=f"CO-OPS Observed (NAVD88)", zorder=3)
ax2.plot(times_3d, d3["values"], color="#E91E63", linewidth=1.0, alpha=0.85,
         label=f"STOFS-3D-Atlantic (NAVD88)", zorder=2)
ax2.axhline(y=0, color="gray", linewidth=0.5, linestyle="--", alpha=0.5)
ax2.set_xlabel("Date (UTC)")
ax2.set_ylabel("Water Elevation (m)")
ax2.set_title("STOFS-3D-Atlantic vs Observations — NAVD88 Datum", fontsize=11)
ax2.legend(loc="upper right", fontsize=9)
ax2.grid(True, alpha=0.3)

ax2.xaxis.set_major_locator(mdates.DayLocator())
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax2.xaxis.set_minor_locator(mdates.HourLocator(byhour=[0, 6, 12, 18]))
fig.autofmt_xdate()

fig.suptitle(
    "STOFS Water Elevation Forecast vs Observations — Newport, RI (Station 8452660)\n"
    f"Cycle: {d2['cycle_date'][:4]}-{d2['cycle_date'][4:6]}-{d2['cycle_date'][6:]} "
    f"{d2['cycle_hour']}z  |  MSL–NAVD88 offset: 0.093 m",
    fontsize=12, y=1.02,
)

plt.tight_layout()
out = "/mnt/d/ocean-mcp/newport_stofs_5day.png"
plt.savefig(out, dpi=150, bbox_inches="tight")
print(f"Saved: {out}")
plt.close()
