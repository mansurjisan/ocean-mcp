"""Tools for profiling NOS OFS run timelines."""

import os
import re
import subprocess

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..server import mcp


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def nos_run_timeline(
    ctx: Context,
    system_name: str,
    days: int = 7,
    account: str | None = None,
) -> str:
    """Profile run timelines for an OFS system over recent cycles.

    Parses Slurm job history to show prep/nowcast/forecast/post timing
    and flags anomalies (stages that took significantly longer than average).

    Args:
        system_name: OFS system name (e.g. 'secofs', 'stofs_3d_atl').
        days: How many days of history to analyze (default 7, max 30).
        account: Slurm account filter. Defaults to current user's jobs.
    """
    days = min(max(1, days), 30)
    user = os.environ.get("USER", "")

    # Build sacct query — look for jobs matching the OFS system name
    from datetime import datetime, timedelta, timezone

    start_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%d"
    )

    cmd = [
        "sacct",
        "--user",
        user,
        "--starttime",
        start_date,
        "-X",
        f"--format=JobID,JobName%50,State,Elapsed,Start,End,ExitCode",
        "--parsable2",
        "--noheader",
    ]
    if account:
        if re.search(r"[;&|`$(){}]", account):
            return f"Error: Unsafe characters in account: '{account}'"
        cmd.extend(["--account", account])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return "Error: sacct not found. Slurm may not be available on this system."
    except subprocess.TimeoutExpired:
        return "Error: sacct timed out."

    if not result.stdout.strip():
        return f"No jobs found for {system_name} in the last {days} days."

    # Parse jobs matching the system name
    stages = {"prep": [], "nowcast": [], "forecast": [], "post": []}
    sys_lower = system_name.lower()

    for line in result.stdout.strip().split("\n"):
        parts = line.split("|")
        if len(parts) < 7:
            continue
        job_name = parts[1].strip().lower()

        # Match jobs for this OFS system
        if sys_lower not in job_name:
            continue

        elapsed = parts[3].strip()
        state = parts[2].strip()

        # Classify into stages
        for stage in stages:
            if stage in job_name:
                elapsed_mins = _parse_elapsed_minutes(elapsed)
                if elapsed_mins is not None:
                    stages[stage].append(
                        {
                            "elapsed_mins": elapsed_mins,
                            "state": state,
                            "start": parts[4].strip(),
                            "elapsed_str": elapsed,
                        }
                    )
                break

    # Build report
    lines = [f"## Run Timeline: {system_name} (last {days} days)\n"]

    has_data = False
    for stage_name, runs in stages.items():
        if not runs:
            continue
        has_data = True
        times = [r["elapsed_mins"] for r in runs]
        avg = sum(times) / len(times)
        max_time = max(times)
        min_time = min(times)
        completed = sum(1 for r in runs if r["state"] == "COMPLETED")
        failed = sum(1 for r in runs if r["state"] != "COMPLETED")

        lines.append(f"### {stage_name.upper()}")
        lines.append(f"- Runs: {len(runs)} ({completed} completed, {failed} failed)")
        lines.append(
            f"- Avg: {avg:.0f} min | Min: {min_time:.0f} min | Max: {max_time:.0f} min"
        )

        # Flag anomalies (>2x average)
        anomalies = [r for r in runs if r["elapsed_mins"] > avg * 2]
        if anomalies:
            lines.append(f"- **ANOMALY**: {len(anomalies)} runs took >2x average:")
            for a in anomalies[:3]:
                lines.append(f"  - {a['start']}: {a['elapsed_str']} ({a['state']})")
        lines.append("")

    if not has_data:
        lines.append(
            f"No matching jobs found for '{system_name}'. "
            f"Job names must contain '{sys_lower}'."
        )

    return "\n".join(lines)


def _parse_elapsed_minutes(elapsed_str: str) -> float | None:
    """Parse Slurm elapsed time format (HH:MM:SS or D-HH:MM:SS) to minutes."""
    try:
        if "-" in elapsed_str:
            days_part, time_part = elapsed_str.split("-", 1)
            days = int(days_part)
        else:
            days = 0
            time_part = elapsed_str

        parts = time_part.split(":")
        if len(parts) == 3:
            hours, minutes, seconds = int(parts[0]), int(parts[1]), int(parts[2])
        elif len(parts) == 2:
            hours, minutes, seconds = 0, int(parts[0]), int(parts[1])
        else:
            return None

        return days * 1440 + hours * 60 + minutes + seconds / 60
    except (ValueError, IndexError):
        return None
