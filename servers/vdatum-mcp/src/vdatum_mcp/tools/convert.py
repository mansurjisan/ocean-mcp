"""Tools for vertical datum conversion."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..server import mcp

_SUPPORTED_DATUMS = [
    "xgeoid20b",
    "navd88",
    "mllw",
    "mlw",
    "mhhw",
    "mhw",
    "lmsl",
    "igld85",
    "lwd",
]

_DATUM_DESCRIPTIONS = {
    "xgeoid20b": "Experimental Geoid 2020B (ITRF2014)",
    "navd88": "North American Vertical Datum of 1988",
    "mllw": "Mean Lower Low Water",
    "mlw": "Mean Low Water",
    "mhhw": "Mean Higher High Water",
    "mhw": "Mean High Water",
    "lmsl": "Local Mean Sea Level",
    "igld85": "International Great Lakes Datum of 1985",
    "lwd": "Low Water Datum (Great Lakes)",
}


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def vdatum_convert(
    ctx: Context,
    datum_from: str,
    datum_to: str,
    lat: str,
    lon: str,
    z: str,
    online: bool = True,
) -> str:
    """Convert elevation values between vertical datums.

    Supports conversions between NAVD88, MLLW, MLW, MHW, MHHW, LMSL,
    xGEOID20b, IGLD85, and LWD using NOAA's coastalmodeling-vdatum.

    Points outside the datum conversion domain return inf.

    Args:
        datum_from: Source vertical datum (e.g. 'navd88', 'mllw').
        datum_to: Target vertical datum (e.g. 'mllw', 'navd88').
        lat: Latitude(s) as comma-separated values or single value (e.g. '30.0' or '30.0,26.0,27.5').
        lon: Longitude(s) as comma-separated values or single value (e.g. '-80.0' or '-80.0,-75.0,-77.5').
        z: Elevation(s) in meters as comma-separated values or single value (e.g. '1.5' or '1.5,0.0,0.1').
        online: If true (default), fetch geotiff grids from AWS. Set false for offline/HPC use.
    """
    import numpy as np

    # Validate datums
    vd_from = datum_from.lower().strip()
    vd_to = datum_to.lower().strip()

    if vd_from not in _SUPPORTED_DATUMS:
        return f"**Error:** Unknown source datum '{datum_from}'. Supported: {', '.join(_SUPPORTED_DATUMS)}"
    if vd_to not in _SUPPORTED_DATUMS:
        return f"**Error:** Unknown target datum '{datum_to}'. Supported: {', '.join(_SUPPORTED_DATUMS)}"
    if vd_from == vd_to:
        return (
            f"Source and target datums are the same ({vd_from}). No conversion needed."
        )

    # Parse numeric inputs
    try:
        lats = [float(x.strip()) for x in lat.split(",")]
        lons = [float(x.strip()) for x in lon.split(",")]
        zs = [float(x.strip()) for x in z.split(",")]
    except ValueError as e:
        return f"**Error:** Invalid numeric input: {e}"

    if not (len(lats) == len(lons) == len(zs)):
        return f"**Error:** lat ({len(lats)}), lon ({len(lons)}), and z ({len(zs)}) must have the same length."

    # Reject out-of-range coordinates up front. Otherwise they pass straight
    # to the VDatum grids, which silently return inf for points outside any
    # domain — indistinguishable from a real conversion failure. (lon is
    # lenient to accept both -180..180 and 0..360 conventions.)
    for v in lats:
        if not -90.0 <= v <= 90.0:
            return f"**Error:** Latitude {v} out of range (must be -90 to 90)."
    for v in lons:
        if not -180.0 <= v <= 360.0:
            return f"**Error:** Longitude {v} out of range (must be -180 to 360)."

    # Convert
    try:
        from .._vendor.coastalmodeling_vdatum import vdatum

        lat_arr = np.array(lats)
        lon_arr = np.array(lons)
        z_arr = np.array(zs)

        clat, clon, cz = vdatum.convert(
            vd_from, vd_to, lat_arr, lon_arr, z_arr, online=online
        )
    except Exception as e:
        return f"**Error:** Conversion failed: {e}"

    # Format results
    cz_list = cz.tolist() if hasattr(cz, "tolist") else [float(cz)]

    lines = [
        "## Vertical Datum Conversion",
        f"**From:** {vd_from.upper()} ({_DATUM_DESCRIPTIONS.get(vd_from, '')})",
        f"**To:** {vd_to.upper()} ({_DATUM_DESCRIPTIONS.get(vd_to, '')})\n",
    ]

    if len(lats) == 1:
        converted = cz_list[0]
        if np.isinf(converted):
            lines.append(
                f"**Result:** Point ({lats[0]}, {lons[0]}) is outside the conversion domain."
            )
        else:
            lines.append(f"**Input:** {zs[0]:.4f} m ({vd_from.upper()})")
            lines.append(f"**Output:** {converted:.4f} m ({vd_to.upper()})")
            lines.append(f"**Difference:** {converted - zs[0]:+.4f} m")
    else:
        lines.append("| Lat | Lon | Input (m) | Output (m) | Diff (m) |")
        lines.append("|-----|-----|-----------|------------|----------|")
        for i in range(len(lats)):
            converted = cz_list[i]
            if np.isinf(converted):
                lines.append(
                    f"| {lats[i]:.4f} | {lons[i]:.4f} | {zs[i]:.4f} | outside domain | — |"
                )
            else:
                diff = converted - zs[i]
                lines.append(
                    f"| {lats[i]:.4f} | {lons[i]:.4f} | {zs[i]:.4f} | {converted:.4f} | {diff:+.4f} |"
                )

    return "\n".join(lines)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def vdatum_list_datums(ctx: Context) -> str:
    """List all supported vertical datums for conversion.

    Shows each datum's abbreviation and full name.
    """
    lines = ["## Supported Vertical Datums\n"]
    lines.append("| Datum | Description |")
    lines.append("|-------|-------------|")
    for datum, desc in _DATUM_DESCRIPTIONS.items():
        lines.append(f"| `{datum}` | {desc} |")

    lines.append(
        "\nNote: Conversions between Great Lakes datums (IGLD85, LWD) "
        "and tidal datums (MLLW, MLW, MHW, MHHW) are not supported."
    )
    return "\n".join(lines)
