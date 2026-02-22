"""Derived product tools: extremes, flood stats, sea level trends, storm events, datums."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import COOPSClient
from ..models import Datum, Units
from ..server import mcp
from ..utils import format_tabular_data, handle_api_error


def _get_client(ctx: Context) -> COOPSClient:
    return ctx.request_context.lifespan_context["coops_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def coops_get_extreme_water_levels(
    ctx: Context,
    station_id: str,
    datum: Datum = Datum.MHHW,
    units: Units = Units.METRIC,
) -> str:
    """Get extreme (record) water levels ever recorded at a CO-OPS station.

    Returns the highest and lowest water levels on record with dates and values.

    Args:
        station_id: CO-OPS station ID (e.g., '8518750' for The Battery, NY).
        datum: Vertical datum reference (default: MHHW).
        units: Unit system — 'metric' or 'english' (default: metric).
    """
    try:
        client = _get_client(ctx)
        params = {
            "name": "extremewaterlevels",
            "station": station_id,
            "datum": datum.value,
            "units": units.value,
        }
        data = await client.fetch_derived("product.json", params)

        extremes = data.get("ExtremeWaterLevels", [])

        if not extremes:
            return f"No extreme water level data available for station {station_id}."

        station_data = extremes[0]
        unit_label = "m" if units == Units.METRIC else "ft"
        lines = [
            f"## Extreme Water Levels \u2014 {station_data.get('stationName', station_id)} ({station_id})"
        ]
        lines.append(
            f"**Datum**: {datum.value} | **Units**: {units.value} | **Epoch**: {station_data.get('epoch', 'N/A')}"
        )
        lines.append("")

        # Extract high and low events from tenYearEvents
        ten_year = station_data.get("tenYearEvents", {})
        highs = ten_year.get("highs", [])
        lows = ten_year.get("lows", [])

        if highs:
            lines.append("### Highest Water Level Events")
            lines.append("| Date | Water Level | Status |")
            lines.append("| --- | --- | --- |")
            for h in highs[:10]:
                level = h.get("level", h.get("value", "N/A"))
                lines.append(
                    f"| {h.get('date', '?')} | {level} {unit_label} | {h.get('status', '?')} |"
                )

        if lows:
            lines.append("\n### Lowest Water Level Events")
            lines.append("| Date | Water Level | Status |")
            lines.append("| --- | --- | --- |")
            for low in lows[:10]:
                level = low.get("level", low.get("value", "N/A"))
                lines.append(
                    f"| {low.get('date', '?')} | {level} {unit_label} | {low.get('status', '?')} |"
                )

        lines.append("\n*Data from NOAA CO-OPS.*")
        return "\n".join(lines)
    except Exception as e:
        return handle_api_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def coops_get_flood_stats(
    ctx: Context,
    station_id: str,
    year: int | None = None,
    datum: Datum = Datum.MHHW,
    units: Units = Units.METRIC,
) -> str:
    """Get annual flood day counts and high tide flooding outlook for a CO-OPS station.

    Combines data from the annual flood count and high tide flooding outlook endpoints.

    Args:
        station_id: CO-OPS station ID (e.g., '8518750' for The Battery, NY).
        year: Optional specific year to query.
        datum: Vertical datum reference (default: MHHW).
        units: Unit system — 'metric' or 'english' (default: metric).
    """
    try:
        client = _get_client(ctx)

        lines = [f"## Flood Statistics \u2014 Station {station_id}"]
        lines.append(f"**Datum**: {datum.value} | **Units**: {units.value}")

        # Fetch annual flood count from htf/htf_annual.json
        flood_params: dict = {"station": station_id}
        if year:
            flood_params["year"] = str(year)

        try:
            flood_data = await client.fetch_derived("htf/htf_annual.json", flood_params)
            flood_counts = flood_data.get("AnnualFloodCount", [])

            if flood_counts:
                lines.append("\n### Annual Flood Day Counts")
                columns = [
                    ("year", "Year"),
                    ("minCount", "Minor"),
                    ("modCount", "Moderate"),
                    ("majCount", "Major"),
                ]
                records = []
                for fc in flood_counts:
                    records.append(
                        {
                            "year": str(fc.get("year", "")),
                            "minCount": str(fc.get("minCount", 0)),
                            "modCount": str(fc.get("modCount", 0)),
                            "majCount": str(fc.get("majCount", 0)),
                        }
                    )
                lines.append(format_tabular_data(records, columns, count_label="years"))
            else:
                lines.append("\n*No annual flood count data returned.*")
        except Exception:
            lines.append("\n*Annual flood count data not available for this station.*")

        # Fetch HTF outlook from htf/htf_met_year_annual_outlook.json
        try:
            outlook_data = await client.fetch_derived(
                "htf/htf_met_year_annual_outlook.json", {"station": station_id}
            )
            outlooks = outlook_data.get("MetYearAnnualOutlook", [])

            if outlooks:
                lines.append("\n### High Tide Flooding Outlook")
                columns = [
                    ("metYear", "Met Year"),
                    ("lowConf", "Low Conf."),
                    ("highConf", "High Conf."),
                    ("projectMethod", "Method"),
                ]
                records = []
                for ol in outlooks:
                    records.append(
                        {
                            "metYear": str(ol.get("metYear", "")),
                            "lowConf": str(ol.get("lowConf", "")),
                            "highConf": str(ol.get("highConf", "")),
                            "projectMethod": ol.get("projectMethod", ""),
                        }
                    )
                lines.append(
                    format_tabular_data(records, columns, count_label="projections")
                )
        except Exception:
            lines.append(
                "\n*High tide flooding outlook not available for this station.*"
            )

        return "\n".join(lines)
    except Exception as e:
        return handle_api_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def coops_get_sea_level_trends(
    ctx: Context,
    station_id: str,
) -> str:
    """Get sea level trend data for a CO-OPS station.

    Returns the long-term linear sea level trend with confidence intervals.

    Args:
        station_id: CO-OPS station ID (e.g., '8518750' for The Battery, NY).
    """
    try:
        client = _get_client(ctx)
        data = await client.fetch_derived(
            "product/sealvltrends.json", {"station": station_id}
        )

        trends_list = data.get("SeaLvlTrends", [])

        if not trends_list:
            return f"No sea level trend data available for station {station_id}."

        trends = trends_list[0]

        lines = [
            f"## Sea Level Trends \u2014 {trends.get('stationName', station_id)} ({station_id})"
        ]

        for key, label in [
            ("trend", "Trend (inches/decade)"),
            ("trendError", "Trend Error (+/-)"),
            ("trendUnits", "Trend Units"),
            ("seasonalAverage", "Seasonal Average"),
            ("seasonalUnits", "Seasonal Units"),
            ("startDate", "Start Date"),
            ("endDate", "End Date"),
            ("latitude", "Latitude"),
            ("longitude", "Longitude"),
        ]:
            val = trends.get(key)
            if val is not None:
                lines.append(f"- **{label}**: {val}")

        return "\n".join(lines)
    except Exception as e:
        return handle_api_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def coops_get_peak_storm_events(
    ctx: Context,
    station_id: str,
    datum: Datum = Datum.MHHW,
    units: Units = Units.METRIC,
    year: int | None = None,
) -> str:
    """Get peak water level events (storm surges) recorded at a CO-OPS station.

    Args:
        station_id: CO-OPS station ID (e.g., '8518750' for The Battery, NY).
        datum: Vertical datum reference (default: MHHW).
        units: Unit system — 'metric' or 'english' (default: metric).
        year: Optional specific year to query.
    """
    try:
        client = _get_client(ctx)
        params: dict = {
            "name": "peakwaterlevels",
            "station": station_id,
            "datum": datum.value,
            "units": units.value,
        }
        if year:
            params["year"] = str(year)

        data = await client.fetch_derived("product.json", params)

        events = data.get("peakWaterLevels", [])

        if not events:
            return f"No peak storm event data available for station {station_id}."

        unit_label = "m" if units == Units.METRIC else "ft"
        columns = [
            ("name", "Event Name"),
            ("eventType", "Type"),
            ("peakValue", f"Peak Level ({unit_label})"),
            ("startDate", "Start Date"),
        ]

        records = []
        for ev in events:
            peak = ev.get("peakValue", ev.get("peak", ev.get("value", "")))
            records.append(
                {
                    "name": ev.get("name", ""),
                    "eventType": ev.get("eventType", ""),
                    "peakValue": str(peak) if peak is not None else "",
                    "startDate": ev.get("startDate", ""),
                }
            )

        return format_tabular_data(
            records,
            columns,
            title=f"Peak Storm Events \u2014 Station {station_id}",
            metadata_lines=[f"Datum: {datum.value}", f"Units: {units.value}"],
            count_label="events",
        )
    except Exception as e:
        return handle_api_error(e)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def coops_get_datums(
    ctx: Context,
    station_id: str,
    units: Units = Units.METRIC,
) -> str:
    """Get tidal datum values for a CO-OPS station.

    Returns datum elevations (MLLW, MHHW, MSL, MHW, MLW, etc.) relative to station datum.

    Args:
        station_id: CO-OPS station ID (e.g., '9414290' for San Francisco, CA).
        units: Unit system — 'metric' or 'english' (default: metric).
    """
    try:
        client = _get_client(ctx)
        data = await client.fetch_metadata(
            f"stations/{station_id}/datums.json", {"units": units.value}
        )

        datums = data.get("datums", [])

        if not datums:
            return f"No datum data available for station {station_id}."

        unit_label = "m" if units == Units.METRIC else "ft"
        columns = [
            ("name", "Datum"),
            ("value", f"Value ({unit_label})"),
            ("description", "Description"),
        ]

        records = []
        for d in datums:
            records.append(
                {
                    "name": d.get("name", d.get("n", "")),
                    "value": d.get("value", d.get("v", "")),
                    "description": d.get("description", d.get("d", "")),
                }
            )

        return format_tabular_data(
            records,
            columns,
            title=f"Tidal Datums \u2014 Station {station_id}",
            metadata_lines=[f"Units: {units.value}"],
            count_label="datums",
        )
    except Exception as e:
        return handle_api_error(e)
