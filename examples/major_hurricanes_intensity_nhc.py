#!/usr/bin/env python3
"""Compare the intensity life-cycles of several catastrophic Atlantic
hurricanes — driven through the MCP protocol.

A reproducible, multi-call NHC example. It spawns the nhc-mcp server as an MCP
stdio subprocess (the same way .mcp.json / an IDE / Claude launches it) and,
for each storm, chains:

  1. nhc_search_storms   resolve the HURDAT2 storm ID from (name, year)
  2. nhc_get_best_track  fetch the observed track + intensity

then overlays the storm tracks on one map and aligns their intensity curves on
a common "hours since genesis" axis so the rapid-intensification phases line up
and can be compared directly.

Storm IDs are discovered, never hard-coded. If one storm can't be retrieved it
is skipped with a warning rather than aborting the run.

Default set: Katrina (2005), Michael (2018), Ian (2022), Milton (2024).

Usage
-----
    python3 examples/major_hurricanes_intensity_nhc.py
    python3 examples/major_hurricanes_intensity_nhc.py \
            --storms "katrina:2005,sandy:2012,maria:2017"

Requires: mcp, matplotlib, numpy (cartopy optional — map degrades to a plain
lon/lat axis without it); `uv` on PATH (servers launched with `uv run`).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parent.parent
CALL_TIMEOUT_S = 120.0
PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf"]
DEFAULT_STORMS = "katrina:2005,michael:2018,ian:2022,milton:2024"


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
    sys.exit("error: `uv` not found on PATH — needed to launch the MCP server.")


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


def _json_or_none(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def parse_dt(s: str) -> datetime | None:
    """HURDAT2 datetime field is 'YYYYMMDD HHMM UTC'."""
    try:
        return datetime.strptime(s, "%Y%m%d %H%M UTC")
    except (ValueError, TypeError):
        return None


async def fetch_storm(name: str, year: int) -> dict[str, Any] | None:
    """search → best_track for one storm; return a normalized record or None."""
    print(f"  MCP → nhc_search_storms (name={name!r}, year={year}, basin=al)")
    s_raw = await call_mcp_tool(
        "servers/nhc-mcp",
        "nhc_mcp",
        "nhc_search_storms",
        {"name": name, "year": year, "basin": "al", "response_format": "json"},
    )
    s = _json_or_none(s_raw)
    storms = (s or {}).get("storms", [])
    if not storms:
        print(f"  ! no HURDAT2 match for {name} {year} — skipping")
        return None
    target = name.strip().upper()
    exact = [x for x in storms if str(x.get("name", "")).upper() == target]

    def peak_of(x: dict[str, Any]) -> int:
        pw = x.get("peak_wind")
        return pw if isinstance(pw, int) else -1

    chosen = max(exact or storms, key=peak_of)
    sid = chosen["id"]

    print(f"  MCP → nhc_get_best_track (storm_id={sid})")
    t_raw = await call_mcp_tool(
        "servers/nhc-mcp",
        "nhc_mcp",
        "nhc_get_best_track",
        {"storm_id": sid, "response_format": "json"},
    )
    t = _json_or_none(t_raw)
    pts = [
        p
        for p in (t or {}).get("track_points", [])
        if p.get("lat") is not None and p.get("lon") is not None
    ]
    if len(pts) < 2:
        print(f"  ! {sid} has too few track points — skipping")
        return None

    winds = [p["max_wind"] for p in pts if p.get("max_wind") is not None]
    press = [p["min_pressure"] for p in pts if p.get("min_pressure") is not None]
    t0 = parse_dt(pts[0]["datetime"])
    t1 = parse_dt(pts[-1]["datetime"])
    return {
        "id": sid,
        "name": str(chosen.get("name", sid)),
        "year": year,
        "points": pts,
        "peak_wind": max(winds) if winds else None,
        "min_pressure": min(press) if press else None,
        "category": chosen.get("category", ""),
        "duration_h": (t1 - t0).total_seconds() / 3600 if t0 and t1 else None,
    }


# --------------------------------------------------------------------------- #
# Plot
# --------------------------------------------------------------------------- #
def make_plot(records: list[dict[str, Any]], out_path: Path) -> None:
    """Tracks overlaid + intensity aligned on hours-since-genesis.

    figsize (12, 12) at dpi=100 -> 1200x1200 px, under the 1600 px rule.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature

        proj = ccrs.PlateCarree()
        have_cartopy = True
    except ImportError:
        have_cartopy = False

    all_lat = [p["lat"] for r in records for p in r["points"]]
    all_lon = [p["lon"] for r in records for p in r["points"]]

    fig = plt.figure(figsize=(12, 12))

    # ---- Panel 1: tracks --------------------------------------------------- #
    if have_cartopy:
        ax_map = fig.add_subplot(2, 1, 1, projection=proj)
        ax_map.set_extent(
            [min(all_lon) - 4, max(all_lon) + 4, min(all_lat) - 4, max(all_lat) + 4],
            crs=proj,
        )
        ax_map.add_feature(cfeature.LAND, facecolor="#ececec", zorder=0)
        ax_map.add_feature(cfeature.OCEAN, facecolor="#d6ecf5", zorder=0)
        ax_map.add_feature(cfeature.COASTLINE, linewidth=0.7, zorder=1)
        ax_map.add_feature(cfeature.STATES, linewidth=0.3, zorder=1)
        tf = {"transform": proj}
    else:
        ax_map = fig.add_subplot(2, 1, 1)
        ax_map.set_xlim(min(all_lon) - 4, max(all_lon) + 4)
        ax_map.set_ylim(min(all_lat) - 4, max(all_lat) + 4)
        ax_map.set_facecolor("#d6ecf5")
        ax_map.set_xlabel("Longitude")
        ax_map.set_ylabel("Latitude")
        tf = {}

    for idx, r in enumerate(records):
        color = PALETTE[idx % len(PALETTE)]
        lons = [p["lon"] for p in r["points"]]
        lats = [p["lat"] for p in r["points"]]
        ax_map.plot(
            lons,
            lats,
            color=color,
            lw=2,
            label=f"{r['name']} {r['year']} ({r['id']})",
            zorder=2,
            **tf,
        )
        peak = max(r["points"], key=lambda p: p.get("max_wind") or 0)
        ax_map.plot(
            peak["lon"],
            peak["lat"],
            marker="*",
            color=color,
            markersize=16,
            markeredgecolor="black",
            markeredgewidth=0.5,
            zorder=3,
            **tf,
        )
    ax_map.legend(loc="lower left", fontsize=8, framealpha=0.9, title="Storm (★=peak)")
    ax_map.set_title(
        "Atlantic Major Hurricanes — HURDAT2 Best Tracks (via nhc-mcp)",
        fontsize=12,
        fontweight="bold",
    )

    # ---- Panel 2: intensity vs hours since genesis ------------------------ #
    ax = fig.add_subplot(2, 1, 2)
    for idx, r in enumerate(records):
        color = PALETTE[idx % len(PALETTE)]
        t0 = parse_dt(r["points"][0]["datetime"])
        xs, ys = [], []
        for p in r["points"]:
            dt = parse_dt(p["datetime"])
            w = p.get("max_wind")
            if dt is None or t0 is None or w is None:
                continue
            xs.append((dt - t0).total_seconds() / 3600.0)
            ys.append(w)
        ax.plot(xs, ys, color=color, lw=2, label=f"{r['name']} {r['year']}")

    for thr, lbl in [(64, "Cat 1"), (96, "Cat 3"), (137, "Cat 5")]:
        ax.axhline(thr, color="gray", lw=0.6, ls="--")
        ax.text(2, thr + 1, lbl, fontsize=7, color="gray")
    ax.set_xlabel("Hours since genesis", fontsize=11)
    ax.set_ylabel("Max sustained wind (kt)", fontsize=11)
    ax.set_title("Intensity life-cycle (aligned at genesis)", fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=9)

    fig.subplots_adjust(left=0.08, right=0.96, top=0.94, bottom=0.06, hspace=0.18)
    fig.savefig(out_path, dpi=100)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
async def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    spec: list[tuple[str, int]] = []
    for tok in args.storms.split(","):
        tok = tok.strip()
        if not tok:
            continue
        nm, _, yr = tok.partition(":")
        try:
            spec.append((nm.strip(), int(yr)))
        except ValueError:
            sys.exit(f"Bad --storms token {tok!r}; expected name:year.")

    records: list[dict[str, Any]] = []
    for nm, yr in spec:
        print(f"[{nm} {yr}]")
        rec = await fetch_storm(nm, yr)
        if rec:
            records.append(rec)

    if len(records) < 2:
        sys.exit("Fewer than 2 storms retrieved — nothing to compare.")

    # ---- Comparison table ------------------------------------------------- #
    print()
    print("=" * 72)
    print("  Atlantic major hurricanes — HURDAT2 (via nhc-mcp)")
    print("=" * 72)
    print(f"  {'Storm':<22}{'ID':<11}{'Peak kt':>8}{'Min mb':>8}{'Days':>7}")
    print(f"  {'-' * 64}")
    for r in sorted(records, key=lambda x: -(x["peak_wind"] or 0)):
        days = f"{r['duration_h'] / 24:.1f}" if r["duration_h"] else "?"
        print(
            f"  {r['name'] + ' ' + str(r['year']):<22}{r['id']:<11}"
            f"{str(r['peak_wind']):>8}{str(r['min_pressure']):>8}{days:>7}"
        )
    print("=" * 72)

    # ---- Artifacts -------------------------------------------------------- #
    png_path = out_dir / "major_hurricanes_intensity_nhc.png"
    json_path = out_dir / "major_hurricanes_intensity_nhc.json"
    make_plot(records, png_path)
    json_path.write_text(
        json.dumps(
            {
                "storms": [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "year": r["year"],
                        "peak_wind_kt": r["peak_wind"],
                        "min_pressure_mb": r["min_pressure"],
                        "duration_h": (
                            round(r["duration_h"], 1) if r["duration_h"] else None
                        ),
                        "track_points": r["points"],
                    }
                    for r in records
                ]
            },
            indent=2,
        )
    )
    print(f"\n  Plot → {png_path}")
    print(f"  Data → {json_path}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(
        description="Compare major-hurricane intensity life-cycles over MCP."
    )
    p.add_argument(
        "--storms",
        default=DEFAULT_STORMS,
        help=f"Comma list of name:year (default {DEFAULT_STORMS!r}).",
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
