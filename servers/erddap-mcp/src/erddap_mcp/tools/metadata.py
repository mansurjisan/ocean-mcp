"""Dataset metadata & info tools."""

from __future__ import annotations

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..client import ERDDAPClient
from ..server import mcp
from ..utils import handle_erddap_error, parse_erddap_json


def _get_client(ctx: Context) -> ERDDAPClient:
    return ctx.request_context.lifespan_context["erddap_client"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def erddap_get_dataset_info(
    ctx: Context,
    server_url: str,
    dataset_id: str,
) -> str:
    """Get detailed metadata for an ERDDAP dataset — variables, dimensions, attributes, time/spatial coverage.

    Args:
        server_url: ERDDAP server URL (e.g., 'https://coastwatch.pfeg.noaa.gov/erddap').
        dataset_id: ERDDAP dataset identifier (e.g., 'erdMH1chlamday').
    """
    try:
        client = _get_client(ctx)
        data = await client.get_info(server_url=server_url, dataset_id=dataset_id)

        rows = parse_erddap_json(data)

        if not rows:
            return f"No info found for dataset '{dataset_id}' on {server_url}."

        # Organize info by category
        global_attrs: dict[str, str] = {}
        variables: dict[str, dict[str, str]] = {}
        dimensions: list[str] = []

        for row in rows:
            row_type = row.get("Row Type", "")
            var_name = row.get("Variable Name", "")
            attr_name = row.get("Attribute Name", "")
            data_type = row.get("Data Type", "")
            value = str(row.get("Value", ""))

            if row_type == "attribute":
                if var_name == "NC_GLOBAL":
                    global_attrs[attr_name] = value
                else:
                    if var_name not in variables:
                        variables[var_name] = {}
                    variables[var_name][attr_name] = value
            elif row_type == "dimension":
                dimensions.append(var_name)
                if var_name not in variables:
                    variables[var_name] = {}
                variables[var_name]["_dimension"] = "true"
                variables[var_name]["_size"] = value
            elif row_type == "variable":
                if var_name not in variables:
                    variables[var_name] = {}
                variables[var_name]["_data_type"] = data_type

        # Build output
        lines = [f"## Dataset Info: {dataset_id}"]
        lines.append(f"**Server**: {server_url}")
        lines.append("")

        # Key global attributes
        key_attrs = [
            ("title", "Title"),
            ("summary", "Summary"),
            ("institution", "Institution"),
            ("cdm_data_type", "Data Type"),
            ("sourceUrl", "Source URL"),
        ]
        for attr_key, label in key_attrs:
            if attr_key in global_attrs:
                val = global_attrs[attr_key]
                if len(val) > 200:
                    val = val[:197] + "..."
                lines.append(f"**{label}**: {val}")

        # Time coverage
        time_start = global_attrs.get("time_coverage_start", "")
        time_end = global_attrs.get("time_coverage_end", "")
        if time_start or time_end:
            lines.append(f"**Time Coverage**: {time_start} to {time_end}")

        # Spatial coverage
        lat_min = global_attrs.get("geospatial_lat_min", "")
        lat_max = global_attrs.get("geospatial_lat_max", "")
        lon_min = global_attrs.get("geospatial_lon_min", "")
        lon_max = global_attrs.get("geospatial_lon_max", "")
        if lat_min or lat_max:
            lines.append(f"**Latitude Range**: {lat_min} to {lat_max}")
        if lon_min or lon_max:
            lines.append(f"**Longitude Range**: {lon_min} to {lon_max}")

        lines.append("")

        # Dimensions
        if dimensions:
            lines.append("### Dimensions")
            for dim in dimensions:
                dim_info = variables.get(dim, {})
                size = dim_info.get("_size", "?")
                lines.append(f"- **{dim}** (size: {size})")
            lines.append("")

        # Variables (non-dimension)
        data_vars = {k: v for k, v in variables.items() if not v.get("_dimension")}
        if data_vars:
            lines.append("### Variables")
            lines.append("| Variable | Type | Units | Long Name |")
            lines.append("| --- | --- | --- | --- |")
            for var_name, attrs in data_vars.items():
                dtype = attrs.get("_data_type", "")
                units = attrs.get("units", "")
                long_name = attrs.get("long_name", attrs.get("ioos_category", ""))
                if len(long_name) > 60:
                    long_name = long_name[:57] + "..."
                lines.append(f"| {var_name} | {dtype} | {units} | {long_name} |")
            lines.append("")

        lines.append(
            "*Use erddap_get_tabledap_data or erddap_get_griddap_data to retrieve data from this dataset.*"
        )

        return "\n".join(lines)

    except Exception as e:
        return handle_erddap_error(e, server_url)
