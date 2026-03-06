"""Statistical summary tools for USGS Water Services."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import USGSClient
from ..models import format_parameter
from ..server import mcp


def _get_client(ctx: Context) -> USGSClient:
    return ctx.request_context.lifespan_context["usgs_client"]


def _handle_error(e: Exception) -> str:
    """Format an exception into a user-friendly error message."""
    import httpx

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 404:
            return "Error: Site not found. Verify the 8-digit USGS site number."
        return f"HTTP Error {status}: The USGS API may be temporarily unavailable."
    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. The USGS API may be experiencing high load."
    return f"Unexpected error: {type(e).__name__}: {e}"


MONTH_NAMES = [
    "",
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def usgs_get_monthly_stats(
    ctx: Context,
    site_number: str,
    parameter_code: str = "00060",
    response_format: str = "markdown",
) -> str:
    """Get monthly streamflow statistics for a USGS site.

    Returns long-term monthly statistics including mean, min, max, and
    percentiles (P10, P25, P50, P75, P90) for each month. Useful for
    understanding seasonal flow patterns.

    Args:
        site_number: 8-digit USGS site number (e.g., '01646500').
        parameter_code: USGS parameter code — '00060' (discharge, default).
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        if not site_number.isdigit() or len(site_number) < 8:
            return "Validation Error: Site number must be at least 8 digits."

        client = _get_client(ctx)
        rows = await client.get_rdb(
            "stat",
            {
                "sites": site_number,
                "statReportType": "monthly",
                "statTypeCd": "all",
                "parameterCd": parameter_code,
            },
        )

        if not rows:
            return f"No monthly statistics found for site {site_number}."

        if response_format == "json":
            import json

            return json.dumps(rows, indent=2)

        # Group by month
        months: dict[str, dict] = {}
        for row in rows:
            month_nu = row.get("month_nu", "")
            if not month_nu:
                continue
            mean_va = row.get("mean_va", "")
            if month_nu not in months:
                months[month_nu] = {}
            months[month_nu]["mean"] = mean_va or months[month_nu].get("mean", "—")
            if row.get("min_va"):
                months[month_nu]["min"] = row["min_va"]
            if row.get("max_va"):
                months[month_nu]["max"] = row["max_va"]

        param_label = format_parameter(parameter_code)
        lines = [f"## Monthly Statistics — Site {site_number}"]
        lines.append(f"**Parameter**: {param_label}")
        lines.append(f"**Records**: {len(rows)} stat rows")
        lines.append("")

        lines.append("| Month | Mean | Min | Max |")
        lines.append("|-------|------|-----|-----|")
        for m_num in sorted(months.keys(), key=lambda x: int(x)):
            m_data = months[m_num]
            try:
                m_name = MONTH_NAMES[int(m_num)]
            except (ValueError, IndexError):
                m_name = m_num
            mean = m_data.get("mean", "—")
            mn = m_data.get("min", "—")
            mx = m_data.get("max", "—")
            lines.append(f"| {m_name} | {mean} | {mn} | {mx} |")

        lines.append("")
        lines.append(
            "*Data from USGS Water Services (monthly statistics). Values in cfs.*"
        )
        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def usgs_get_daily_stats(
    ctx: Context,
    site_number: str,
    parameter_code: str = "00060",
    month: int | None = None,
    response_format: str = "markdown",
) -> str:
    """Get daily streamflow statistics (flow duration) for a USGS site.

    Returns percentiles showing the typical flow range for each day of the
    year based on the complete period of record. Useful for understanding
    whether current conditions are normal for the time of year.

    Args:
        site_number: 8-digit USGS site number (e.g., '01646500').
        parameter_code: USGS parameter code — '00060' (discharge, default).
        month: Optional month number (1-12) to filter results.
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        if not site_number.isdigit() or len(site_number) < 8:
            return "Validation Error: Site number must be at least 8 digits."

        if month is not None and (month < 1 or month > 12):
            return "Validation Error: Month must be between 1 and 12."

        client = _get_client(ctx)
        rows = await client.get_rdb(
            "stat",
            {
                "sites": site_number,
                "statReportType": "daily",
                "statTypeCd": "all",
                "parameterCd": parameter_code,
            },
        )

        if not rows:
            return f"No daily statistics found for site {site_number}."

        # Filter by month if requested
        if month is not None:
            rows = [r for r in rows if r.get("month_nu") == str(month)]
            if not rows:
                return f"No daily statistics found for site {site_number} in month {month}."

        if response_format == "json":
            import json

            return json.dumps(rows, indent=2)

        param_label = format_parameter(parameter_code)
        month_label = f" — {MONTH_NAMES[month]}" if month else ""
        lines = [f"## Daily Statistics — Site {site_number}{month_label}"]
        lines.append(f"**Parameter**: {param_label}")
        lines.append(f"**Records**: {len(rows)} days")
        lines.append("")

        lines.append("| Month | Day | Mean | P25 | P50 | P75 | Min | Max |")
        lines.append("|-------|-----|------|-----|-----|-----|-----|-----|")
        display = rows[:60]
        for row in display:
            m = row.get("month_nu", "")
            d = row.get("day_nu", "")
            mean = row.get("mean_va", "—")
            p25 = row.get("p25_va", "—")
            p50 = row.get("p50_va", "—")
            p75 = row.get("p75_va", "—")
            mn = row.get("min_va", "—")
            mx = row.get("max_va", "—")
            lines.append(
                f"| {m} | {d} | {mean} | {p25} | {p50} | {p75} | {mn} | {mx} |"
            )

        if len(rows) > 60:
            lines.append(f"\n*Showing first 60 of {len(rows)} daily records.*")

        lines.append("")
        lines.append(
            "*Data from USGS Water Services (daily statistics). Values in cfs.*"
        )
        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)
