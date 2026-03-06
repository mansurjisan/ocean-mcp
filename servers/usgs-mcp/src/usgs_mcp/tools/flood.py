"""Flood analysis tools for USGS Water Services."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import USGSClient
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


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def usgs_get_peak_streamflow(
    ctx: Context,
    site_number: str,
    start_year: int | None = None,
    end_year: int | None = None,
    response_format: str = "markdown",
) -> str:
    """Get annual peak streamflow records for a USGS site.

    Returns the highest flow recorded each year, including discharge and
    gage height. Many sites have 50+ years of record. Useful for flood
    frequency analysis and understanding historical flood severity.

    Args:
        site_number: 8-digit USGS site number (e.g., '01646500').
        start_year: Optional start year filter.
        end_year: Optional end year filter.
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        if not site_number.isdigit() or len(site_number) < 8:
            return "Validation Error: Site number must be at least 8 digits."

        params: dict = {"site_no": site_number}
        if start_year:
            params["begin_date"] = f"{start_year}-01-01"
        if end_year:
            params["end_date"] = f"{end_year}-12-31"

        client = _get_client(ctx)
        rows = await client.get_peak(params)

        if not rows:
            return f"No peak streamflow records found for site {site_number}."

        if response_format == "json":
            import json

            return json.dumps(rows, indent=2)

        # Find the period of record max
        max_flow = 0.0
        max_row = None
        for row in rows:
            try:
                flow = float(row.get("peak_va", "0"))
                if flow > max_flow:
                    max_flow = flow
                    max_row = row
            except (ValueError, TypeError):
                pass

        lines = [f"## Peak Streamflow — Site {site_number}"]
        lines.append(f"**Records**: {len(rows)} years")
        if max_row:
            lines.append(
                f"**Period of Record Max**: {max_flow:,.0f} cfs on {max_row.get('peak_dt', '?')}"
            )
        lines.append("")

        lines.append("| Date | Discharge (cfs) | Gage Height (ft) | Code |")
        lines.append("|------|-----------------|-------------------|------|")
        for row in rows:
            date = row.get("peak_dt", "—")
            flow = row.get("peak_va", "—")
            ght = row.get("gage_ht", "—")
            code = row.get("peak_cd", "")
            marker = " **MAX**" if row is max_row else ""
            lines.append(f"| {date} | {flow}{marker} | {ght} | {code} |")

        lines.append("")
        lines.append("*Data from USGS Water Services (peak streamflow).*")
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
async def usgs_get_flood_status(
    ctx: Context,
    site_number: str,
    response_format: str = "markdown",
) -> str:
    """Assess current flood conditions at a USGS site.

    Combines current instantaneous data with peak flow history and
    statistical context to determine whether conditions are normal,
    above normal, or at flood stage.

    Args:
        site_number: 8-digit USGS site number (e.g., '01646500').
        response_format: Output format — 'markdown' (default) or 'json'.
    """
    try:
        if not site_number.isdigit() or len(site_number) < 8:
            return "Validation Error: Site number must be at least 8 digits."

        client = _get_client(ctx)

        # Fetch current value
        iv_data = await client.get_json(
            "iv",
            {
                "sites": site_number,
                "parameterCd": "00060",
                "period": "P1D",
            },
        )

        ts_list = iv_data.get("value", {}).get("timeSeries", [])
        if not ts_list:
            return f"No current data available for site {site_number}."

        ts = ts_list[0]
        site_name = ts.get("sourceInfo", {}).get("siteName", site_number)
        unit = ts.get("variable", {}).get("unit", {}).get("unitCode", "cfs")

        all_vals = []
        for val_set in ts.get("values", []):
            all_vals.extend(val_set.get("value", []))

        if not all_vals:
            return f"No current readings for site {site_number}."

        latest = all_vals[-1]
        try:
            current_flow = float(latest.get("value", "0"))
        except (ValueError, TypeError):
            return f"Error: Could not parse current flow value for site {site_number}."

        current_time = latest.get("dateTime", "")

        # Fetch peak history
        peak_flow = None
        peak_date = None
        try:
            peak_rows = await client.get_peak({"site_no": site_number})
            for row in peak_rows:
                try:
                    flow = float(row.get("peak_va", "0"))
                    if peak_flow is None or flow > peak_flow:
                        peak_flow = flow
                        peak_date = row.get("peak_dt", "?")
                except (ValueError, TypeError):
                    pass
        except Exception:
            pass

        # Fetch monthly stats for context
        median_flow = None
        try:
            from datetime import UTC, datetime

            now = datetime.now(UTC)
            stat_rows = await client.get_rdb(
                "stat",
                {
                    "sites": site_number,
                    "statReportType": "daily",
                    "statTypeCd": "median",
                    "parameterCd": "00060",
                },
            )
            month_str = f"{now.month}"
            day_str = f"{now.day}"
            for sr in stat_rows:
                if sr.get("month_nu") == month_str and sr.get("day_nu") == day_str:
                    try:
                        median_flow = float(sr.get("p50_va", ""))
                    except (ValueError, TypeError):
                        pass
                    break
        except Exception:
            pass

        # Determine status
        status = "Normal"
        if median_flow and median_flow > 0:
            ratio = current_flow / median_flow
            if ratio > 5.0:
                status = "Major Flood"
            elif ratio > 3.0:
                status = "Moderate Flood"
            elif ratio > 2.0:
                status = "Flood"
            elif ratio > 1.5:
                status = "Above Normal"
            elif ratio < 0.5:
                status = "Below Normal"

        pct_of_peak = None
        if peak_flow and peak_flow > 0:
            pct_of_peak = round(current_flow / peak_flow * 100, 1)

        result = {
            "site_number": site_number,
            "site_name": site_name,
            "current_flow_cfs": current_flow,
            "current_time": current_time,
            "status": status,
        }
        if median_flow is not None:
            result["median_flow_cfs"] = median_flow
            result["pct_of_median"] = (
                round(current_flow / median_flow * 100, 1) if median_flow > 0 else None
            )
        if peak_flow is not None:
            result["peak_of_record_cfs"] = peak_flow
            result["peak_of_record_date"] = peak_date
            result["pct_of_peak"] = pct_of_peak

        if response_format == "json":
            import json

            return json.dumps(result, indent=2)

        lines = [f"## Flood Status — {site_name}"]
        lines.append(f"**Site**: {site_number}")
        lines.append(f"**Status**: **{status}**")
        lines.append(f"**Current Flow**: {current_flow:,.1f} {unit}")
        lines.append(f"**As of**: {current_time}")
        lines.append("")

        if median_flow is not None:
            pct = result.get("pct_of_median")
            lines.append(f"**Historical Median (today)**: {median_flow:,.1f} {unit}")
            if pct is not None:
                lines.append(f"**Current vs Median**: {pct:.0f}%")

        if peak_flow is not None:
            lines.append(f"**Peak of Record**: {peak_flow:,.0f} {unit} ({peak_date})")
            if pct_of_peak is not None:
                lines.append(f"**Current vs Peak**: {pct_of_peak:.1f}%")

        lines.append("")
        lines.append("### Status Categories")
        lines.append("- **Normal**: Within typical range for this time of year")
        lines.append("- **Above Normal**: 1.5–2x median flow")
        lines.append("- **Flood**: 2–3x median flow")
        lines.append("- **Moderate Flood**: 3–5x median flow")
        lines.append("- **Major Flood**: >5x median flow")

        lines.append("")
        lines.append(
            "*Data from USGS Water Services. Flood status is approximate and based on historical statistics.*"
        )
        return "\n".join(lines)
    except Exception as e:
        return _handle_error(e)
