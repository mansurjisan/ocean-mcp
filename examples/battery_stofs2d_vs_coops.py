#!/usr/bin/env python3
"""Compare STOFS-2D-Global forecast water levels against CO-OPS tide-gauge
observations — driven entirely through the MCP protocol.

This is an end-to-end, reproducible example: it spawns two ocean-mcp servers
(stofs-mcp and coops-mcp) as MCP stdio subprocesses — exactly the way an MCP
client (Claude, an IDE, .mcp.json) launches them — performs the MCP handshake,
calls one tool on each server, then aligns and scores the two time series.

No data is hard-coded. Every number in the output and plot comes from a live
MCP tool call.

  1. stofs-mcp   → stofs_get_station_forecast   (STOFS-2D-Global, cwl, JSON)
  2. coops-mcp   → coops_get_water_levels        (observed, JSON)

Datum note — the one real subtlety here
----------------------------------------
STOFS-2D-Global water levels are referenced to **LMSL** (local mean sea
level). CO-OPS does not expose an "LMSL" datum, but its **MSL** datum is the
operational equivalent for a tidal station. We therefore request the CO-OPS
observations in MSL so the two series share a vertical reference. A residual
offset of ~1–5 cm between LMSL and MSL is expected and is left visible in the
bias rather than tuned away.

Observations only exist for the past, so the comparison is restricted to the
forecast cycle's nowcast / early-forecast hours that now lie before "now".
Pick a cycle ~2 days old (the default) to get a solid overlap window.

Usage
-----
    python3 examples/battery_stofs2d_vs_coops.py
    python3 examples/battery_stofs2d_vs_coops.py --station 8443970 \
            --cycle-date 2026-05-15 --cycle-hour 00 --max-hours 72

Requires: mcp, matplotlib, numpy in the running interpreter; `uv` on PATH
(the servers are launched with `uv run --directory ...`, same as .mcp.json).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parent.parent
TIME_FMT = "%Y-%m-%d %H:%M"  # both STOFS and CO-OPS emit this exact format
CALL_TIMEOUT_S = 240.0  # STOFS downloads a station NetCDF; allow generous time


# --------------------------------------------------------------------------- #
# MCP plumbing
# --------------------------------------------------------------------------- #
def _uv() -> str:
    """Locate the `uv` launcher (same one .mcp.json relies on)."""
    found = shutil.which("uv")
    if found:
        return found
    fallback = Path.home() / "miniconda3" / "bin" / "uv"
    if fallback.exists():
        return str(fallback)
    sys.exit("error: `uv` not found on PATH — needed to launch the MCP servers.")


async def call_mcp_tool(
    server_dir: str,
    module: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Spawn one ocean-mcp server over stdio, call a single tool, return its text.

    Mirrors the launch line in .mcp.json:
        uv run --directory servers/<x> python -m <module>
    """
    params = StdioServerParameters(
        command=_uv(),
        args=[
            "run",
            "--directory",
            str(REPO_ROOT / server_dir),
            "python",
            "-m",
            module,
        ],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=60.0)
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments=arguments),
                timeout=CALL_TIMEOUT_S,
            )

    if not result.content:
        raise RuntimeError(f"{tool_name} returned no content")
    text = getattr(result.content[0], "text", "")
    if result.isError:
        raise RuntimeError(f"{tool_name} reported an error:\n{text}")
    return text


def _parse_json_or_die(text: str, what: str) -> dict[str, Any]:
    """Tool returned JSON on success, or a plain-text error message on failure."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        sys.exit(f"\n{what} did not return JSON — the tool said:\n\n{text}\n")


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #
def compute_stats(model: list[float], obs: list[float]) -> dict[str, float]:
    """Bias, RMSE, MAE, peak |error| and Pearson R for two aligned series."""
    import numpy as np

    m = np.asarray(model, dtype=float)
    o = np.asarray(obs, dtype=float)
    err = m - o
    r = float(np.corrcoef(m, o)[0, 1]) if len(m) > 1 else float("nan")
    return {
        "bias": round(float(err.mean()), 4),
        "rmse": round(float(np.sqrt((err**2).mean())), 4),
        "mae": round(float(np.abs(err).mean()), 4),
        "peak_error": round(float(np.abs(err).max()), 4),
        "correlation": round(r, 4),
        "n": int(len(m)),
    }


# --------------------------------------------------------------------------- #
# Plot
# --------------------------------------------------------------------------- #
def make_plot(
    times: list[datetime],
    model: list[float],
    obs: list[float],
    stats: dict[str, float],
    station: str,
    cycle: str,
    out_path: Path,
) -> None:
    """Two-panel figure: water-level overlay + error residual.

    Sized for the repo image rule: figsize (12, 7) at dpi=100 -> 1200x700 px,
    well under the 1600 px longest-side limit.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    errors = [m - o for m, o in zip(model, obs)]

    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(12, 7),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08},
    )

    ax1.plot(times, obs, color="#1f77b4", lw=1.8, label="CO-OPS observed (MSL)")
    ax1.plot(
        times,
        model,
        color="#ff7f0e",
        lw=1.5,
        ls="--",
        label="STOFS-2D-Global (LMSL)",
    )
    ax1.axhline(0, color="gray", lw=0.8, ls=":")
    ax1.set_ylabel("Water level (m)", fontsize=11)
    ax1.set_title(
        f"STOFS-2D-Global vs CO-OPS Observations\nStation {station} — Cycle {cycle}",
        fontsize=12,
        fontweight="bold",
    )
    ax1.legend(loc="upper left", fontsize=10)
    ax1.grid(True, alpha=0.35)

    stats_text = (
        f"Bias: {stats['bias']:+.3f} m\n"
        f"RMSE: {stats['rmse']:.3f} m\n"
        f"MAE:  {stats['mae']:.3f} m\n"
        f"R:    {stats['correlation']:.4f}\n"
        f"N:    {stats['n']}"
    )
    ax1.text(
        0.985,
        0.97,
        stats_text,
        transform=ax1.transAxes,
        fontsize=9,
        va="top",
        ha="right",
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#cccccc", alpha=0.85),
    )

    ax2.fill_between(
        times,
        errors,
        0,
        where=[e >= 0 for e in errors],
        color="#d62728",
        alpha=0.55,
        label="model high",
    )
    ax2.fill_between(
        times,
        errors,
        0,
        where=[e < 0 for e in errors],
        color="#1f77b4",
        alpha=0.55,
        label="model low",
    )
    ax2.axhline(0, color="black", lw=0.9)
    ax2.set_ylabel("Error (m)", fontsize=11)
    ax2.set_xlabel("Time (UTC)", fontsize=11)
    ax2.legend(loc="upper left", fontsize=9, ncol=2)
    ax2.grid(True, alpha=0.35)

    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%Hz"))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=6))

    # Explicit margins (not tight_layout — incompatible with the shared-x
    # gridspec height-ratio layout and would emit a UserWarning).
    fig.subplots_adjust(left=0.075, right=0.985, top=0.90, bottom=0.12)
    fig.savefig(out_path, dpi=100)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
async def run(args: argparse.Namespace) -> int:
    station = args.station
    cycle_date = args.cycle_date or (
        datetime.now(timezone.utc) - timedelta(days=2)
    ).strftime("%Y-%m-%d")
    cycle_hour = args.cycle_hour
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. STOFS-2D-Global forecast, via the stofs-mcp server -------------- #
    print(
        f"[1/2] MCP → stofs-mcp : stofs_get_station_forecast "
        f"(station={station}, 2d_global, cwl, cycle {cycle_date} {cycle_hour}z)"
    )
    stofs_raw = await call_mcp_tool(
        "servers/stofs-mcp",
        "stofs_mcp",
        "stofs_get_station_forecast",
        {
            "station_id": station,
            "model": "2d_global",
            "product": "cwl",
            "cycle_date": cycle_date,
            "cycle_hour": cycle_hour,
            "response_format": "json",
        },
    )
    stofs = _parse_json_or_die(stofs_raw, "stofs_get_station_forecast")
    stofs_times: list[str] = stofs["times"]
    stofs_values: list[float] = stofs["values"]
    stofs_datum = stofs.get("datum", "LMSL")
    if not stofs_times:
        sys.exit("STOFS returned an empty series for this station/cycle.")

    # Restrict to the past portion of the forecast (observations exist only
    # up to ~now), capped at --max-hours from the cycle start.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    t0 = datetime.strptime(stofs_times[0], TIME_FMT)
    horizon = min(now, t0 + timedelta(hours=args.max_hours))
    keep = [
        (t, v)
        for t, v in zip(stofs_times, stofs_values)
        if v is not None and datetime.strptime(t, TIME_FMT) <= horizon
    ]
    if not keep:
        sys.exit(
            "No STOFS samples fall in the past — the cycle is too recent for an "
            "observation comparison. Pick an older --cycle-date (e.g. 2-3 days "
            "ago)."
        )
    stofs_clip = dict(keep)
    win_start = datetime.strptime(keep[0][0], TIME_FMT)
    win_end = datetime.strptime(keep[-1][0], TIME_FMT)
    print(
        f"      STOFS datum={stofs_datum}  points={len(keep)}  "
        f"window {win_start:%Y-%m-%d %H:%M} → {win_end:%Y-%m-%d %H:%M} UTC"
    )

    # ---- 2. CO-OPS observed water levels, via the coops-mcp server --------- #
    # Request MSL to match STOFS LMSL (CO-OPS has no LMSL datum).
    print(
        f"[2/2] MCP → coops-mcp : coops_get_water_levels "
        f"(station={station}, datum=MSL, 6-min, gmt)"
    )
    coops_raw = await call_mcp_tool(
        "servers/coops-mcp",
        "coops_mcp",
        "coops_get_water_levels",
        {
            "station_id": station,
            "begin_date": win_start.strftime("%Y-%m-%d"),
            "end_date": (win_end + timedelta(days=1)).strftime("%Y-%m-%d"),
            "datum": "MSL",
            "units": "metric",
            "interval": "6",
            "time_zone": "gmt",
            "response_format": "json",
        },
    )
    coops = _parse_json_or_die(coops_raw, "coops_get_water_levels")
    obs_records = coops.get("data", {}).get("data", [])
    obs_map: dict[str, float] = {}
    for rec in obs_records:
        t_str, v_str = rec.get("t", ""), rec.get("v", "")
        if not t_str or v_str in ("", " ", None):
            continue
        try:
            obs_map[t_str] = float(v_str)
        except (TypeError, ValueError):
            continue
    if not obs_map:
        sys.exit(
            f"CO-OPS returned no usable observations for station {station} in "
            f"{win_start:%Y-%m-%d} → {win_end:%Y-%m-%d}. The station may lack "
            "real-time water level data for this period."
        )
    print(f"      CO-OPS datum=MSL  observations={len(obs_map)}")

    # ---- 3. Align on identical 6-min timestamps & score -------------------- #
    aligned_t: list[datetime] = []
    aligned_model: list[float] = []
    aligned_obs: list[float] = []
    for t_str, m_val in sorted(stofs_clip.items()):
        if t_str in obs_map:
            aligned_t.append(datetime.strptime(t_str, TIME_FMT))
            aligned_model.append(m_val)
            aligned_obs.append(obs_map[t_str])

    if len(aligned_t) < 2:
        sys.exit(
            "STOFS and CO-OPS series share fewer than 2 timestamps — cannot "
            "compare. Likely a too-recent cycle or a station without 6-min "
            "observations."
        )

    stats = compute_stats(aligned_model, aligned_obs)
    cycle_label = (
        f"{stofs['cycle_date'][:4]}-{stofs['cycle_date'][4:6]}-"
        f"{stofs['cycle_date'][6:]} {stofs['cycle_hour']}z"
    )

    # ---- 4. Report -------------------------------------------------------- #
    print()
    print("=" * 64)
    print(f"  STOFS-2D-Global vs CO-OPS  —  Station {station}")
    print(f"  Cycle {cycle_label}   |   STOFS {stofs_datum} vs CO-OPS MSL")
    print(f"  Lat/Lon: {stofs.get('lat', '?')}, {stofs.get('lon', '?')}")
    print("=" * 64)
    print(f"  Bias (model - obs) : {stats['bias']:+.3f} m")
    print(f"  RMSE               : {stats['rmse']:.3f} m")
    print(f"  MAE                : {stats['mae']:.3f} m")
    print(f"  Peak |error|       : {stats['peak_error']:.3f} m")
    print(f"  Correlation (R)    : {stats['correlation']:.4f}")
    print(f"  Matched points     : {stats['n']}")
    print("=" * 64)

    step = max(1, len(aligned_t) // 24)
    print("\n  Time (UTC)         STOFS    Obs     Error")
    print(f"  {'-' * 46}")
    for i in range(0, len(aligned_t), step):
        print(
            f"  {aligned_t[i]:%Y-%m-%d %H:%M}  "
            f"{aligned_model[i]:7.3f}  {aligned_obs[i]:6.3f}  "
            f"{aligned_model[i] - aligned_obs[i]:+6.3f}"
        )

    # ---- 5. Artifacts ----------------------------------------------------- #
    png_path = out_dir / f"battery_stofs2d_vs_coops_{station}.png"
    json_path = out_dir / f"battery_stofs2d_vs_coops_{station}.json"
    make_plot(
        aligned_t,
        aligned_model,
        aligned_obs,
        stats,
        station,
        cycle_label,
        png_path,
    )
    json_path.write_text(
        json.dumps(
            {
                "station_id": station,
                "cycle": cycle_label,
                "stofs_datum": stofs_datum,
                "coops_datum": "MSL",
                "lat": stofs.get("lat"),
                "lon": stofs.get("lon"),
                "statistics": stats,
                "series": [
                    {
                        "time": t.strftime(TIME_FMT),
                        "stofs_m": m,
                        "obs_m": o,
                        "error_m": round(m - o, 4),
                    }
                    for t, m, o in zip(aligned_t, aligned_model, aligned_obs)
                ],
            },
            indent=2,
        )
    )
    print(f"\n  Plot → {png_path}")
    print(f"  Data → {json_path}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(
        description="Compare STOFS-2D-Global vs CO-OPS water levels over MCP."
    )
    p.add_argument(
        "--station",
        default="8518750",
        help="CO-OPS station ID (default 8518750, The Battery NY).",
    )
    p.add_argument(
        "--cycle-date",
        default=None,
        help="STOFS cycle date YYYY-MM-DD (default: 2 days ago, UTC).",
    )
    p.add_argument(
        "--cycle-hour",
        default="00",
        help="STOFS cycle hour: 00/06/12/18 (default 00).",
    )
    p.add_argument(
        "--max-hours",
        type=int,
        default=72,
        help="Max forecast hours from cycle start to compare (default 72).",
    )
    p.add_argument(
        "--out-dir",
        default=str(REPO_ROOT / "examples"),
        help="Directory for the PNG/JSON artifacts (default: examples/).",
    )
    args = p.parse_args()
    try:
        sys.exit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
