"""Tools: recon_list_sfmr and recon_get_sfmr — SFMR radial wind profile analysis."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import ReconClient
from ..models import AIRCRAFT_CODES
from ..server import mcp
from ..utils import (
    cleanup_temp_file,
    compute_radial_wind_profile,
    format_json_response,
    handle_recon_error,
    parse_atcf_best_track,
    parse_directory_listing,
    parse_sfmr_netcdf,
)


def _get_client(ctx: Context) -> ReconClient:
    return ctx.request_context.lifespan_context["recon_client"]


def _decode_sfmr_filename(filename: str) -> dict:
    """Extract aircraft code, date, and mission from an SFMR filename.

    Filename pattern: AFRC_SFMR{YYYYMMDD}{AircraftLetter}{Seq}.nc
    or: {AGENCY}_SFMR{YYYYMMDD}{AircraftLetter}{Seq}.nc

    Examples:
        AFRC_SFMR20220926H1.nc -> aircraft='H', date='20220926', seq='1'
        NOAA_SFMR20200825U2.nc -> aircraft='U', date='20200825', seq='2'
    """
    info = {"filename": filename, "date": None, "aircraft_code": None, "aircraft": None, "mission_seq": None}

    # Extract the part after SFMR
    import re

    match = re.search(r"SFMR(\d{8})([A-Z])(\d+)", filename)
    if match:
        info["date"] = match.group(1)
        info["aircraft_code"] = match.group(2)
        info["aircraft"] = AIRCRAFT_CODES.get(match.group(2), f"Unknown ({match.group(2)})")
        info["mission_seq"] = match.group(3)

    return info


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def recon_list_sfmr(
    ctx: Context,
    year: int,
    storm_name: str,
    response_format: str = "markdown",
) -> str:
    """List available SFMR NetCDF files for a storm from the AOML archive.

    SFMR (Stepped-Frequency Microwave Radiometer) files contain 1-Hz
    surface wind speed and rain rate observations from hurricane hunter
    aircraft. Data is post-processed and quality-controlled by AOML/HRD.

    Note: AOML posts data weeks to months after storms. Recent storms
    may not have SFMR data available yet.

    Args:
        year: Year of the storm (e.g., 2022).
        storm_name: Lowercase storm name (e.g., 'ian', 'laura').
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        client = _get_client(ctx)
        url = client.build_sfmr_url(year, storm_name)
        html = await client.list_directory(url)
        entries = parse_directory_listing(html)

        # Filter to .nc files only
        nc_entries = [e for e in entries if e["filename"].endswith(".nc")]

        if not nc_entries:
            return (
                f"## SFMR Files — {storm_name.title()} ({year})\n\n"
                f"No SFMR NetCDF files found at {url}\n\n"
                f"AOML may not have posted data yet for this storm, "
                f"or the storm name may be different. Data is typically "
                f"available weeks to months after the storm."
            )

        # Decode filenames
        decoded = []
        for entry in nc_entries:
            info = _decode_sfmr_filename(entry["filename"])
            decoded.append(info)

        # Sort by date
        decoded.sort(key=lambda d: d.get("date") or "")

        if response_format == "json":
            return format_json_response(
                decoded,
                context=f"SFMR files for {storm_name.title()} ({year}) from AOML archive",
            )

        lines = [
            f"## SFMR Files — {storm_name.title()} ({year})",
            f"**Source:** AOML HRD Archive | **URL:** {url}",
            "",
            "| Filename | Date | Aircraft | Mission |",
            "| --- | --- | --- | --- |",
        ]

        for d in decoded:
            date_fmt = d["date"] or "—"
            if d["date"] and len(d["date"]) == 8:
                date_fmt = f"{d['date'][:4]}-{d['date'][4:6]}-{d['date'][6:]}"
            lines.append(
                f"| {d['filename']} | {date_fmt} "
                f"| {d['aircraft'] or '—'} | {d['mission_seq'] or '—'} |"
            )

        lines.append("")
        lines.append(f"*{len(decoded)} SFMR files available. Data from AOML HRD Archive.*")

        return "\n".join(lines)

    except Exception as e:
        return handle_recon_error(e, f"listing SFMR files for {storm_name} ({year})")


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def recon_get_sfmr(
    ctx: Context,
    year: int,
    storm_name: str,
    storm_number: int,
    basin: str = "al",
    filename: str | None = None,
    bin_size_km: float = 5.0,
    max_radius_km: float = 500.0,
    response_format: str = "markdown",
) -> str:
    """Get SFMR radial wind profile for a storm — surface wind speed vs. distance from center.

    Downloads SFMR NetCDF data from the AOML archive and computes each
    observation's radial distance from the storm center using the ATCF
    best track. Returns binned wind statistics (mean, max, count) by
    radius.

    Requires the storm's ATCF identifiers (basin + storm_number) to
    fetch the best track for radius computation.

    Note: AOML posts data weeks to months after storms. Recent storms
    may not have SFMR data available yet.

    Args:
        year: Year of the storm (e.g., 2022).
        storm_name: Lowercase storm name (e.g., 'ian', 'laura').
        storm_number: ATCF storm number within the season (e.g., 9 for AL09).
        basin: Basin code — 'al' (Atlantic, default), 'ep' (East Pacific).
        filename: Specific SFMR filename to process. If None, processes up to 10 files.
        bin_size_km: Radial bin width in km (default 5).
        max_radius_km: Maximum radius to include in km (default 500).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    temp_files: list = []
    try:
        client = _get_client(ctx)

        # 1. Fetch best track (tries active btk/ then archived .gz)
        try:
            bdeck_text = await client.fetch_best_track(basin, storm_number, year)
        except Exception as e:
            return handle_recon_error(
                e, f"fetching best track for {basin.upper()}{storm_number:02d}{year}"
            )

        track = parse_atcf_best_track(bdeck_text)
        if not track:
            return (
                f"No best track data found for {basin.upper()}{storm_number:02d}{year}. "
                f"Cannot compute radial distances without a track."
            )

        # 2. Get list of SFMR files
        sfmr_url = client.build_sfmr_url(year, storm_name)

        if filename:
            filenames_to_process = [filename]
        else:
            html = await client.list_directory(sfmr_url)
            entries = parse_directory_listing(html)
            nc_entries = [e for e in entries if e["filename"].endswith(".nc")]
            nc_entries.sort(key=lambda e: e["filename"])
            filenames_to_process = [e["filename"] for e in nc_entries[:10]]

        if not filenames_to_process:
            return (
                f"## SFMR Radial Wind Profile — {storm_name.title()} ({year})\n\n"
                f"No SFMR NetCDF files found at {sfmr_url}"
            )

        # 3. Process each file
        all_missions: list[dict] = []

        for fname in filenames_to_process:
            file_url = sfmr_url + fname
            tmp_path = None
            try:
                tmp_path = await client.download_netcdf(file_url)
                temp_files.append(tmp_path)

                sfmr_data = parse_sfmr_netcdf(tmp_path)
                profile = compute_radial_wind_profile(
                    sfmr_data, track,
                    bin_size_km=bin_size_km,
                    max_radius_km=max_radius_km,
                )

                file_info = _decode_sfmr_filename(fname)

                mission = {
                    "filename": fname,
                    "date": file_info.get("date"),
                    "aircraft": file_info.get("aircraft", "Unknown"),
                    "n_obs": sfmr_data["n_obs"],
                    "profile": profile,
                }

                # Find peak wind
                if profile:
                    peak_bin = max(profile, key=lambda b: b["max_wind_ms"])
                    mission["peak_wind_ms"] = peak_bin["max_wind_ms"]
                    mission["peak_radius_km"] = f"{peak_bin['radius_min_km']:.0f}-{peak_bin['radius_max_km']:.0f}"

                all_missions.append(mission)

            except Exception:
                continue

        if not all_missions:
            return (
                f"## SFMR Radial Wind Profile — {storm_name.title()} ({year})\n\n"
                f"Could not process any SFMR files. The files may be in an "
                f"unexpected format or the best track may not overlap the "
                f"flight times."
            )

        if response_format == "json":
            return format_json_response(
                {
                    "storm": storm_name.title(),
                    "year": year,
                    "basin": basin.upper(),
                    "storm_id": f"{basin.upper()}{storm_number:02d}{year}",
                    "track_points": len(track),
                    "bin_size_km": bin_size_km,
                    "max_radius_km": max_radius_km,
                    "missions": all_missions,
                },
                context=f"SFMR radial wind profiles for {storm_name.title()} ({year})",
            )

        # Format markdown output
        lines = [f"## SFMR Radial Wind Profile — {storm_name.title()} ({year})"]
        lines.append(
            f"**Storm ID:** {basin.upper()}{storm_number:02d}{year} "
            f"| **Track points:** {len(track)} "
            f"| **Bin size:** {bin_size_km} km"
        )
        lines.append("")

        for mission in all_missions:
            date_fmt = mission["date"] or "Unknown"
            if mission["date"] and len(mission["date"]) == 8:
                d = mission["date"]
                date_fmt = f"{d[:4]}-{d[4:6]}-{d[6:]}"

            lines.append(f"### Mission: {mission['filename']}")
            lines.append(
                f"**Aircraft:** {mission['aircraft']} "
                f"| **Date:** {date_fmt} "
                f"| **Observations:** {mission['n_obs']:,}"
            )
            lines.append("")

            profile = mission["profile"]
            if not profile:
                lines.append("*No valid radial wind data for this mission.*")
                lines.append("")
                continue

            lines.append("| Radius (km) | Mean Wind (m/s) | Max Wind (m/s) | Samples |")
            lines.append("| --- | --- | --- | --- |")

            for b in profile:
                lines.append(
                    f"| {b['radius_min_km']:.0f}-{b['radius_max_km']:.0f} "
                    f"| {b['mean_wind_ms']} "
                    f"| {b['max_wind_ms']} "
                    f"| {b['samples']} |"
                )

            if "peak_wind_ms" in mission:
                lines.append("")
                lines.append(
                    f"**Peak:** {mission['peak_wind_ms']} m/s "
                    f"at {mission['peak_radius_km']} km radius"
                )

            lines.append("")

        lines.append(
            f"*{len(all_missions)} mission(s) processed. "
            f"Data from AOML HRD SFMR Archive.*"
        )

        return "\n".join(lines)

    except Exception as e:
        return handle_recon_error(e, f"processing SFMR data for {storm_name} ({year})")
    finally:
        for fp in temp_files:
            cleanup_temp_file(fp)
