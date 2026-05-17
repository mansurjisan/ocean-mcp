#!/usr/bin/env python3
"""Hurricane Katrina (2005) best-track analysis — driven through the MCP protocol.

An end-to-end, reproducible NHC example. It spawns the nhc-mcp server as an MCP
stdio subprocess — exactly the way an MCP client (Claude, an IDE, .mcp.json)
launches it — performs the MCP handshake, and chains two tool calls:

  1. nhc_search_storms   discover the storm ID for "Katrina" 2005 in HURDAT2
  2. nhc_get_best_track  fetch the full observed track for that ID

Nothing is hard-coded — the storm ID is *discovered* from the search rather
than assumed (Katrina is AL122005, the 12th Atlantic storm of 2005; the
nhc_get_best_track docstring's "AL092005" hint is wrong, which is exactly why
searching first is the robust pattern).

Output: a Saffir-Simpson-coloured track map plus a wind/pressure intensity
timeline, and a JSON dump of the track.

Usage
-----
    python3 examples/katrina_besttrack_nhc.py
    python3 examples/katrina_besttrack_nhc.py --name michael --year 2018

Requires: mcp, matplotlib, numpy in the running interpreter (cartopy optional —
the map degrades to a plain lon/lat axis without it); `uv` on PATH (the server
is launched with `uv run --directory ...`, same as .mcp.json).
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

# Saffir-Simpson colour ramp — keys match nhc_mcp.models.SAFFIR_SIMPSON labels.
SS_COLORS = {
    "Tropical Depression": "#5ebaff",
    "Tropical Storm": "#00faf4",
    "Category 1": "#ffffcc",
    "Category 2": "#ffe775",
    "Category 3": "#ffc140",
    "Category 4": "#ff8f20",
    "Category 5": "#ff6060",
}
SS_THRESHOLDS = [
    (137, "Category 5"),
    (113, "Category 4"),
    (96, "Category 3"),
    (83, "Category 2"),
    (64, "Category 1"),
    (34, "Tropical Storm"),
    (0, "Tropical Depression"),
]


# --------------------------------------------------------------------------- #
# MCP plumbing (same pattern as battery_stofs2d_vs_coops.py)
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


def classify(wind_kt: float | None) -> str:
    """Local Saffir-Simpson fallback when a track point lacks a category."""
    if wind_kt is None:
        return "Tropical Depression"
    for threshold, label in SS_THRESHOLDS:
        if wind_kt >= threshold:
            return label
    return "Tropical Depression"


def parse_dt(s: str) -> datetime | None:
    """HURDAT2 datetime field is 'YYYYMMDD HHMM UTC'."""
    try:
        return datetime.strptime(s, "%Y%m%d %H%M UTC")
    except (ValueError, TypeError):
        return None


# --------------------------------------------------------------------------- #
# Plot
# --------------------------------------------------------------------------- #
def make_plot(
    storm_id: str,
    storm_name: str,
    source: str,
    pts: list[dict[str, Any]],
    out_path: Path,
) -> None:
    """Track map (SS-coloured) over a wind/pressure intensity timeline.

    figsize (12, 11) at dpi=100 -> 1200x1100 px, under the 1600 px rule.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt

    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature

        proj = ccrs.PlateCarree()
        have_cartopy = True
    except ImportError:
        have_cartopy = False

    lats = [p["lat"] for p in pts]
    lons = [p["lon"] for p in pts]
    fig = plt.figure(figsize=(12, 11))

    # ---- Panel 1: track map ------------------------------------------------ #
    if have_cartopy:
        ax_map = fig.add_subplot(2, 1, 1, projection=proj)
        ax_map.set_extent(
            [min(lons) - 4, max(lons) + 4, min(lats) - 4, max(lats) + 4],
            crs=proj,
        )
        ax_map.add_feature(cfeature.LAND, facecolor="#ececec", zorder=0)
        ax_map.add_feature(cfeature.OCEAN, facecolor="#d6ecf5", zorder=0)
        ax_map.add_feature(cfeature.COASTLINE, linewidth=0.7, zorder=1)
        ax_map.add_feature(cfeature.STATES, linewidth=0.3, zorder=1)
        tf = {"transform": proj}
    else:
        ax_map = fig.add_subplot(2, 1, 1)
        ax_map.set_xlim(min(lons) - 4, max(lons) + 4)
        ax_map.set_ylim(min(lats) - 4, max(lats) + 4)
        ax_map.set_facecolor("#d6ecf5")
        ax_map.set_xlabel("Longitude")
        ax_map.set_ylabel("Latitude")
        tf = {}

    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        cat = a.get("category") or classify(a.get("max_wind"))
        ax_map.plot(
            [a["lon"], b["lon"]],
            [a["lat"], b["lat"]],
            color=SS_COLORS.get(cat, "#888888"),
            linewidth=3,
            solid_capstyle="round",
            zorder=2,
            **tf,
        )
    for p in pts:
        cat = p.get("category") or classify(p.get("max_wind"))
        ax_map.plot(
            p["lon"],
            p["lat"],
            "o",
            color=SS_COLORS.get(cat, "#888888"),
            markersize=6,
            markeredgecolor="black",
            markeredgewidth=0.4,
            zorder=3,
            **tf,
        )

    peak = max(pts, key=lambda p: p.get("max_wind") or 0)
    ax_map.plot(
        peak["lon"],
        peak["lat"],
        marker="*",
        color="black",
        markersize=18,
        zorder=4,
        **tf,
    )
    ax_map.legend(
        handles=[mpatches.Patch(color=c, label=lbl) for lbl, c in SS_COLORS.items()],
        loc="lower left",
        fontsize=8,
        title="Saffir-Simpson",
        framealpha=0.9,
    )
    ax_map.set_title(
        f"Hurricane {storm_name} ({storm_id}) — {source} Best Track\n"
        f"★ peak {peak.get('max_wind')} kt / {peak.get('min_pressure')} mb",
        fontsize=12,
        fontweight="bold",
    )

    # ---- Panel 2: intensity timeline -------------------------------------- #
    ax_w = fig.add_subplot(2, 1, 2)
    t = [parse_dt(p["datetime"]) for p in pts]
    valid = [(tt, p) for tt, p in zip(t, pts) if tt is not None]
    tt = [v[0] for v in valid]
    wind = [v[1].get("max_wind") for v in valid]
    pres = [v[1].get("min_pressure") for v in valid]

    ax_w.plot(tt, wind, color="#1f77b4", lw=2, label="Max wind (kt)")
    ax_w.set_ylabel("Max wind (kt)", color="#1f77b4", fontsize=11)
    ax_w.tick_params(axis="y", labelcolor="#1f77b4")
    ax_w.grid(True, alpha=0.3)
    for thr, lbl in [(64, "Cat 1"), (96, "Cat 3"), (137, "Cat 5")]:
        ax_w.axhline(thr, color="gray", lw=0.6, ls="--")
        ax_w.text(tt[0], thr + 1, lbl, fontsize=7, color="gray")

    ax_p = ax_w.twinx()
    ax_p.plot(tt, pres, color="#d62728", lw=1.6, ls="--", label="Min pressure (mb)")
    ax_p.set_ylabel("Min pressure (mb)", color="#d62728", fontsize=11)
    ax_p.tick_params(axis="y", labelcolor="#d62728")
    ax_p.invert_yaxis()  # deeper pressure = stronger storm, plot it "up"

    ax_w.set_title("Intensity life-cycle", fontsize=11)
    ax_w.set_xlabel("Date (UTC)", fontsize=11)
    ax_w.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax_w.xaxis.set_major_locator(mdates.DayLocator())
    lines = ax_w.get_lines()[:1] + ax_p.get_lines()[:1]
    ax_w.legend(lines, [ln.get_label() for ln in lines], loc="upper left", fontsize=9)
    fig.autofmt_xdate(rotation=0, ha="center")

    fig.subplots_adjust(left=0.08, right=0.92, top=0.93, bottom=0.07, hspace=0.22)
    fig.savefig(out_path, dpi=100)
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
async def run(args: argparse.Namespace) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- 1. Discover the storm ID via HURDAT2 search ---------------------- #
    print(
        f"[1/2] MCP → nhc-mcp : nhc_search_storms "
        f"(name={args.name!r}, year={args.year}, basin=al)"
    )
    search_raw = await call_mcp_tool(
        "servers/nhc-mcp",
        "nhc_mcp",
        "nhc_search_storms",
        {
            "name": args.name,
            "year": args.year,
            "basin": "al",
            "response_format": "json",
        },
    )
    search = _parse_json_or_die(search_raw, "nhc_search_storms")
    storms = search.get("storms", [])
    if not storms:
        sys.exit(
            f"No HURDAT2 storm matched name={args.name!r} year={args.year}. "
            "Try a different --name/--year."
        )
    # Prefer an exact name match; among those pick the strongest (peak wind).
    target = args.name.strip().upper()

    def peak_of(s: dict[str, Any]) -> int:
        pw = s.get("peak_wind")
        return pw if isinstance(pw, int) else -1

    exact = [s for s in storms if str(s.get("name", "")).upper() == target]
    chosen = max(exact or storms, key=peak_of)
    storm_id = chosen["id"]
    print(
        f"      → {chosen.get('name')} {storm_id} "
        f"(peak {chosen.get('peak_wind')} kt, {chosen.get('category')}, "
        f"{chosen.get('track_points')} track points)"
    )

    # ---- 2. Fetch the full best track ------------------------------------ #
    print(f"[2/2] MCP → nhc-mcp : nhc_get_best_track (storm_id={storm_id})")
    track_raw = await call_mcp_tool(
        "servers/nhc-mcp",
        "nhc_mcp",
        "nhc_get_best_track",
        {"storm_id": storm_id, "response_format": "json"},
    )
    track = _parse_json_or_die(track_raw, "nhc_get_best_track")
    pts = [
        p
        for p in track.get("track_points", [])
        if p.get("lat") is not None and p.get("lon") is not None
    ]
    if len(pts) < 2:
        sys.exit(f"Best track for {storm_id} has too few valid points to plot.")

    source = track.get("source", "HURDAT2")
    name = str(chosen.get("name", storm_id))

    # ---- 3. Summary ------------------------------------------------------- #
    winds = [p["max_wind"] for p in pts if p.get("max_wind") is not None]
    press = [p["min_pressure"] for p in pts if p.get("min_pressure") is not None]
    peak = max(pts, key=lambda p: p.get("max_wind") or 0)
    t0, t1 = parse_dt(pts[0]["datetime"]), parse_dt(pts[-1]["datetime"])

    print()
    print("=" * 64)
    print(f"  Hurricane {name} — {storm_id}  (source: {source})")
    print("=" * 64)
    print(f"  Track points     : {len(pts)}")
    if t0 and t1:
        span_h = (t1 - t0).total_seconds() / 3600
        print(f"  Active period    : {t0:%Y-%m-%d %H:%M} → {t1:%Y-%m-%d %H:%M} UTC")
        print(f"  Duration         : {span_h:.0f} h ({span_h / 24:.1f} days)")
    print(
        f"  Peak intensity   : {max(winds)} kt "
        f"({classify(max(winds))}) at "
        f"{peak.get('lat')}N, {abs(peak.get('lon')):.1f}W"
    )
    if press:
        print(f"  Min pressure     : {min(press)} mb")
    print("=" * 64)

    # ---- 4. Artifacts ----------------------------------------------------- #
    png_path = out_dir / f"katrina_besttrack_nhc_{storm_id}.png"
    json_path = out_dir / f"katrina_besttrack_nhc_{storm_id}.json"
    make_plot(storm_id, name, source, pts, png_path)
    json_path.write_text(
        json.dumps(
            {
                "storm_id": storm_id,
                "name": name,
                "source": source,
                "peak_wind_kt": max(winds) if winds else None,
                "min_pressure_mb": min(press) if press else None,
                "track_points": pts,
            },
            indent=2,
        )
    )
    print(f"\n  Plot → {png_path}")
    print(f"  Data → {json_path}")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(
        description="Hurricane best-track analysis over MCP (NHC HURDAT2)."
    )
    p.add_argument(
        "--name",
        default="katrina",
        help="Storm name to search (default 'katrina').",
    )
    p.add_argument(
        "--year",
        type=int,
        default=2005,
        help="Storm year (default 2005).",
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
