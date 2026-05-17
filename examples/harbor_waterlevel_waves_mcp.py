#!/usr/bin/env python3
"""Water level + waves at New York Harbor — three MCP servers, one picture.

A reproducible, multi-server MCP demo. It spawns three ocean-mcp servers as
MCP stdio subprocesses (the same `uv run` lines as .mcp.json), performs the
handshake, and chains four tool calls:

  1. stofs-mcp  stofs_get_station_forecast  STOFS-2D-Global water level (LMSL)
  2. coops-mcp  coops_get_water_levels      CO-OPS observed water level
  3. ndbc-mcp   ndbc_get_observations       NDBC water level at the co-located
                                            Battery gauge (batn6, TIDE)
  4. ndbc-mcp   ndbc_get_observations       NDBC significant wave height at an
                                            offshore buoy (44025, WVHT)

Honest-by-construction (verified against live NDBC, 2026-05-17)
---------------------------------------------------------------
NDBC realtime2 does **not** carry water level for the NY-area NOS gauges —
`batn6` (the NDBC feed of the very same Battery station as CO-OPS 8518750)
reports `TIDE = MM` in every record, as do Robbins Reef / Sandy Hook / Kings
Point. So this example *requests* NDBC water level and then reports the true
availability instead of faking a series: for these stations CO-OPS is the
authoritative water-level source. NDBC's solid contribution here is **wave
height** from a real offshore wave buoy (44025, ~30 NM S of Islip) — the
in-situ sea state that a barotropic surge model like STOFS-2D does not
forecast at all.

If a future/other NDBC station *does* report TIDE, the script picks it up
automatically (realtime2 TIDE is in feet → converted to metres for the plot).

Usage
-----
    python3 examples/harbor_waterlevel_waves_mcp.py
    python3 examples/harbor_waterlevel_waves_mcp.py --wave-buoy 44065 \
            --cycle-date 2026-05-15 --cycle-hour 00 --max-hours 60

Requires: mcp, matplotlib, numpy; `uv` on PATH (servers launched with
`uv run --directory ...`, same as .mcp.json).
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
TIME_FMT = "%Y-%m-%d %H:%M"  # STOFS + CO-OPS emit this exact format
FT_TO_M = 0.3048  # NDBC realtime2 TIDE column is in feet
CALL_TIMEOUT_S = 240.0


# --------------------------------------------------------------------------- #
# MCP plumbing (same pattern as the other MCP examples)
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
    """Spawn one ocean-mcp server over stdio, call a single tool, return its text."""
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


def _ndbc_dt(s: str) -> datetime | None:
    """ndbc_get_observations emits ISO 8601 (datetime.isoformat())."""
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


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
    wl_t: list[datetime],
    stofs: list[float],
    obs: list[float],
    ndbc_wl: tuple[list[datetime], list[float]] | None,
    wave: tuple[list[datetime], list[float]],
    stats: dict[str, float],
    station: str,
    cycle: str,
    wave_buoy: str,
    ndbc_wl_note: str,
    out_path: Path,
) -> None:
    """Top: water level (STOFS vs CO-OPS [+NDBC if any]). Bottom: NDBC Hs.

    figsize (12, 9) at dpi=100 -> 1200x900 px, under the 1600 px rule.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(12, 9),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 2], "hspace": 0.1},
    )

    # ---- Panel 1: water level --------------------------------------------- #
    ax1.plot(wl_t, obs, color="#1f77b4", lw=1.8, label="CO-OPS observed (MSL)")
    ax1.plot(
        wl_t, stofs, color="#ff7f0e", lw=1.5, ls="--", label="STOFS-2D-Global (LMSL)"
    )
    if ndbc_wl is not None:
        ax1.plot(
            ndbc_wl[0],
            ndbc_wl[1],
            color="#2ca02c",
            lw=1.4,
            marker=".",
            ms=3,
            label=f"NDBC {station} TIDE",
        )
    ax1.axhline(0, color="gray", lw=0.8, ls=":")
    ax1.set_ylabel("Water level (m)", fontsize=11)
    ax1.set_title(
        f"New York Harbor — Water Level & Waves via 3 MCP servers\n"
        f"Battery {station} | STOFS cycle {cycle}",
        fontsize=12,
        fontweight="bold",
    )
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(True, alpha=0.35)

    stats_text = (
        f"STOFS vs CO-OPS\n"
        f"Bias: {stats['bias']:+.3f} m\n"
        f"RMSE: {stats['rmse']:.3f} m\n"
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
    ax1.text(
        0.015,
        0.04,
        ndbc_wl_note,
        transform=ax1.transAxes,
        fontsize=8,
        va="bottom",
        ha="left",
        color="#555",
        bbox=dict(boxstyle="round,pad=0.3", fc="#fffbe6", ec="#e0c97f", alpha=0.9),
    )

    # ---- Panel 2: NDBC significant wave height ---------------------------- #
    wt, wv = wave
    ax2.plot(wt, wv, color="#17557e", lw=1.6)
    ax2.fill_between(wt, wv, alpha=0.18, color="#17557e")
    ax2.set_ylabel("Sig. wave height Hs (m)", fontsize=11)
    ax2.set_xlabel("Time (UTC)", fontsize=11)
    ax2.set_title(
        f"NDBC buoy {wave_buoy} — significant wave height "
        f"(in-situ sea state; STOFS-2D does not forecast waves)",
        fontsize=10,
    )
    ax2.grid(True, alpha=0.35)
    if wv:
        ax2.set_ylim(0, max(wv) * 1.25 + 0.1)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%Hz"))
    ax2.xaxis.set_major_locator(mdates.HourLocator(interval=6))
    fig.autofmt_xdate(rotation=0, ha="center")

    fig.subplots_adjust(left=0.075, right=0.985, top=0.91, bottom=0.1)
    fig.savefig(out_path, dpi=100)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
async def run(args: argparse.Namespace) -> int:
    station = args.wl_station
    ndbc_wl_station = args.ndbc_wl_station
    wave_buoy = args.wave_buoy
    cycle_date = args.cycle_date or (
        datetime.now(timezone.utc) - timedelta(days=2)
    ).strftime("%Y-%m-%d")
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. STOFS-2D-Global ----------------------------------------------- #
    print(
        f"[1/4] MCP → stofs-mcp : stofs_get_station_forecast "
        f"({station}, 2d_global, cwl, {cycle_date} {args.cycle_hour}z)"
    )
    stofs = _parse_json_or_die(
        await call_mcp_tool(
            "servers/stofs-mcp",
            "stofs_mcp",
            "stofs_get_station_forecast",
            {
                "station_id": station,
                "model": "2d_global",
                "product": "cwl",
                "cycle_date": cycle_date,
                "cycle_hour": args.cycle_hour,
                "response_format": "json",
            },
        ),
        "stofs_get_station_forecast",
    )
    if not stofs.get("times"):
        sys.exit("STOFS returned an empty series for this station/cycle.")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    t0 = datetime.strptime(stofs["times"][0], TIME_FMT)
    horizon = min(now, t0 + timedelta(hours=args.max_hours))
    keep = [
        (t, v)
        for t, v in zip(stofs["times"], stofs["values"])
        if v is not None and datetime.strptime(t, TIME_FMT) <= horizon
    ]
    if not keep:
        sys.exit(
            "STOFS cycle too recent for an observation overlap — use an older one."
        )
    stofs_clip = dict(keep)
    win_start = datetime.strptime(keep[0][0], TIME_FMT)
    win_end = datetime.strptime(keep[-1][0], TIME_FMT)
    win_hours = (win_end - win_start).total_seconds() / 3600
    print(
        f"      STOFS {stofs.get('datum')} pts={len(keep)} "
        f"window {win_start:%Y-%m-%d %H:%M} → {win_end:%Y-%m-%d %H:%M} UTC"
    )

    # ---- 2. CO-OPS observed (MSL ≈ STOFS LMSL) ---------------------------- #
    print(f"[2/4] MCP → coops-mcp : coops_get_water_levels ({station}, MSL, 6-min)")
    coops = _parse_json_or_die(
        await call_mcp_tool(
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
        ),
        "coops_get_water_levels",
    )
    obs_map: dict[str, float] = {}
    for rec in coops.get("data", {}).get("data", []):
        t_str, v_str = rec.get("t", ""), rec.get("v", "")
        if not t_str or v_str in ("", " ", None):
            continue
        try:
            obs_map[t_str] = float(v_str)
        except (TypeError, ValueError):
            continue
    if not obs_map:
        sys.exit(f"CO-OPS returned no usable observations for {station}.")
    print(f"      CO-OPS MSL observations={len(obs_map)}")

    # ---- 3. NDBC water level at the co-located gauge (honest probe) ------- #
    ndbc_hours = max(1, min(1080, int(win_hours) + 6))
    print(
        f"[3/4] MCP → ndbc-mcp  : ndbc_get_observations "
        f"({ndbc_wl_station}, TIDE, {ndbc_hours}h)"
    )
    ndbc_wl_raw = _parse_json_or_die(
        await call_mcp_tool(
            "servers/ndbc-mcp",
            "ndbc_mcp",
            "ndbc_get_observations",
            {
                "station_id": ndbc_wl_station,
                "hours": ndbc_hours,
                "variables": ["TIDE"],
                "response_format": "json",
            },
        ),
        "ndbc_get_observations (TIDE)",
    )
    ndbc_wl_t: list[datetime] = []
    ndbc_wl_v: list[float] = []
    for r in ndbc_wl_raw.get("records", []):
        dt = _ndbc_dt(r.get("datetime", ""))
        tide = r.get("TIDE")
        if dt is not None and tide is not None:
            ndbc_wl_t.append(dt)
            ndbc_wl_v.append(float(tide) * FT_TO_M)  # realtime2 TIDE is feet
    ndbc_wl_available = len(ndbc_wl_v) > 0
    if ndbc_wl_available:
        ndbc_wl_note = (
            f"NDBC {ndbc_wl_station} TIDE: {len(ndbc_wl_v)} pts (ft→m), overlaid above"
        )
        print(f"      NDBC {ndbc_wl_station} TIDE points={len(ndbc_wl_v)}")
    else:
        ndbc_wl_note = (
            f"NDBC {ndbc_wl_station} TIDE: not reported (= MM) — typical for NOS\n"
            f"gauges in the NDBC feed; CO-OPS is the authoritative water level."
        )
        print(
            f"      NDBC {ndbc_wl_station} TIDE: not reported (verified MM) — "
            f"CO-OPS is authoritative for NOS water level"
        )

    # ---- 4. NDBC significant wave height (offshore buoy) ------------------ #
    print(
        f"[4/4] MCP → ndbc-mcp  : ndbc_get_observations "
        f"({wave_buoy}, WVHT, {ndbc_hours}h)"
    )
    wave_raw = _parse_json_or_die(
        await call_mcp_tool(
            "servers/ndbc-mcp",
            "ndbc_mcp",
            "ndbc_get_observations",
            {
                "station_id": wave_buoy,
                "hours": ndbc_hours,
                "variables": ["WVHT"],
                "response_format": "json",
            },
        ),
        "ndbc_get_observations (WVHT)",
    )
    wave_t: list[datetime] = []
    wave_v: list[float] = []
    for r in wave_raw.get("records", []):
        dt = _ndbc_dt(r.get("datetime", ""))
        wvht = r.get("WVHT")
        if (
            dt is not None
            and wvht is not None
            and win_start <= dt <= win_end + timedelta(hours=6)
        ):
            wave_t.append(dt)
            wave_v.append(float(wvht))
    if not wave_v:
        sys.exit(
            f"NDBC buoy {wave_buoy} reported no WVHT in the window. Pick another "
            f"--wave-buoy (44025 is the reliable Long Island wave buoy)."
        )
    # NDBC is newest-first; sort ascending for plotting
    wave_pairs = sorted(zip(wave_t, wave_v))
    wave_t = [p[0] for p in wave_pairs]
    wave_v = [p[1] for p in wave_pairs]
    print(f"      NDBC {wave_buoy} WVHT points={len(wave_v)}")

    # ---- Align STOFS vs CO-OPS & score ------------------------------------ #
    aligned_t, a_stofs, a_obs = [], [], []
    for t_str, m_val in sorted(stofs_clip.items()):
        if t_str in obs_map:
            aligned_t.append(datetime.strptime(t_str, TIME_FMT))
            a_stofs.append(m_val)
            a_obs.append(obs_map[t_str])
    if len(aligned_t) < 2:
        sys.exit("STOFS and CO-OPS share <2 timestamps — use an older cycle.")
    stats = compute_stats(a_stofs, a_obs)
    cycle_label = (
        f"{stofs['cycle_date'][:4]}-{stofs['cycle_date'][4:6]}-"
        f"{stofs['cycle_date'][6:]} {stofs['cycle_hour']}z"
    )

    # ---- Report ----------------------------------------------------------- #
    print()
    print("=" * 66)
    print("  New York Harbor — Water Level & Waves (3 MCP servers)")
    print(f"  Battery {station} | STOFS cycle {cycle_label}")
    print("=" * 66)
    print("  Water level — STOFS-2D vs CO-OPS (MSL):")
    print(
        f"    Bias {stats['bias']:+.3f} m | RMSE {stats['rmse']:.3f} m | "
        f"R {stats['correlation']:.4f} | N {stats['n']}"
    )
    print(
        f"  NDBC {ndbc_wl_station} water level (TIDE): "
        f"{'available, ' + str(len(ndbc_wl_v)) + ' pts' if ndbc_wl_available else 'NOT reported (MM)'}"
    )
    print(f"  NDBC {wave_buoy} significant wave height (WVHT):")
    print(
        f"    min {min(wave_v):.2f} m | mean {sum(wave_v) / len(wave_v):.2f} m | "
        f"max {max(wave_v):.2f} m | N {len(wave_v)}"
    )
    print("=" * 66)

    # ---- Artifacts -------------------------------------------------------- #
    png_path = out_dir / f"harbor_waterlevel_waves_{station}.png"
    json_path = out_dir / f"harbor_waterlevel_waves_{station}.json"
    make_plot(
        aligned_t,
        a_stofs,
        a_obs,
        (ndbc_wl_t, ndbc_wl_v) if ndbc_wl_available else None,
        (wave_t, wave_v),
        stats,
        station,
        cycle_label,
        wave_buoy,
        ndbc_wl_note,
        png_path,
    )
    json_path.write_text(
        json.dumps(
            {
                "battery_station": station,
                "ndbc_wl_station": ndbc_wl_station,
                "wave_buoy": wave_buoy,
                "stofs_cycle": cycle_label,
                "stofs_datum": stofs.get("datum"),
                "coops_datum": "MSL",
                "waterlevel_stats_stofs_vs_coops": stats,
                "ndbc_waterlevel_available": ndbc_wl_available,
                "ndbc_waterlevel_note": ndbc_wl_note.replace("\n", " "),
                "waterlevel_series": [
                    {"time": t.strftime(TIME_FMT), "stofs_m": s, "coops_m": o}
                    for t, s, o in zip(aligned_t, a_stofs, a_obs)
                ],
                "wave_height_series": [
                    {"time": t.strftime(TIME_FMT), "hs_m": v}
                    for t, v in zip(wave_t, wave_v)
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
        description="Water level + waves at NY Harbor over 3 MCP servers."
    )
    p.add_argument("--wl-station", default="8518750", help="CO-OPS station (Battery).")
    p.add_argument(
        "--ndbc-wl-station",
        default="batn6",
        help="NDBC station co-located with the gauge (default batn6 = 8518750).",
    )
    p.add_argument(
        "--wave-buoy",
        default="44025",
        help="NDBC wave buoy for WVHT (default 44025, S of Islip — reliable).",
    )
    p.add_argument(
        "--cycle-date", default=None, help="STOFS cycle YYYY-MM-DD (default 2d ago)."
    )
    p.add_argument("--cycle-hour", default="00", help="STOFS cycle hour (default 00).")
    p.add_argument(
        "--max-hours", type=int, default=72, help="Max forecast hours (default 72)."
    )
    p.add_argument(
        "--out-dir",
        default=str(REPO_ROOT / "examples"),
        help="Directory for PNG/JSON artifacts (default: examples/).",
    )
    args = p.parse_args()
    try:
        sys.exit(asyncio.run(run(args)))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
