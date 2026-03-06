"""Core parsers for ADCIRC input files."""

from __future__ import annotations

import math


def parse_fort15(text: str) -> dict:
    """Parse an ADCIRC fort.15 control file into a structured dictionary.

    This is a state-machine parser that handles the positional, context-dependent
    format of fort.15. It parses the most common configurations and gracefully
    skips sections it cannot parse.
    """
    lines = text.strip().splitlines()
    result: dict = {"_raw_lines": len(lines), "_warnings": []}
    i = 0

    def _next_line() -> str | None:
        nonlocal i
        while i < len(lines):
            line = lines[i].strip()
            i += 1
            if line:
                return line
        return None

    def _read_value(line: str) -> str:
        """Extract the value part before any inline comment (! character)."""
        if "!" in line:
            return line[: line.index("!")].strip()
        return line.strip()

    def _safe_int(val: str, default: int = 0) -> int:
        try:
            return int(val.split()[0])
        except (ValueError, IndexError):
            return default

    def _safe_float(val: str, default: float = 0.0) -> float:
        try:
            return float(val.split()[0])
        except (ValueError, IndexError):
            return default

    try:
        # Line 1: RUNDES
        line = _next_line()
        if line is None:
            return result
        result["RUNDES"] = line

        # Line 2: RUNID
        line = _next_line()
        if line is None:
            return result
        result["RUNID"] = line

        # Line 3: NFOVER
        line = _next_line()
        if line is None:
            return result
        result["NFOVER"] = _safe_int(_read_value(line))

        # Line 4: NABOUT
        line = _next_line()
        if line is None:
            return result
        result["NABOUT"] = _safe_int(_read_value(line))

        # Line 5: NSCREEN
        line = _next_line()
        if line is None:
            return result
        result["NSCREEN"] = _safe_int(_read_value(line))

        # Line 6: IHOT
        line = _next_line()
        if line is None:
            return result
        result["IHOT"] = _safe_int(_read_value(line))

        # Line 7: ICS
        line = _next_line()
        if line is None:
            return result
        result["ICS"] = _safe_int(_read_value(line))

        # Line 8: IM
        line = _next_line()
        if line is None:
            return result
        result["IM"] = _safe_int(_read_value(line))

        # Line 9: NOLIBF NOLIFA NOLICA NOLICAT
        line = _next_line()
        if line is None:
            return result
        parts = _read_value(line).split()
        result["NOLIBF"] = int(parts[0]) if len(parts) > 0 else 0
        result["NOLIFA"] = int(parts[1]) if len(parts) > 1 else 0
        result["NOLICA"] = int(parts[2]) if len(parts) > 2 else 0
        result["NOLICAT"] = int(parts[3]) if len(parts) > 3 else 0

        # Line 10: NWP
        line = _next_line()
        if line is None:
            return result
        result["NWP"] = _safe_int(_read_value(line))

        # NWP attribute names
        result["nodal_attributes"] = []
        for _ in range(result["NWP"]):
            attr_line = _next_line()
            if attr_line:
                result["nodal_attributes"].append(attr_line.strip())

        # NCOR
        line = _next_line()
        if line is None:
            return result
        result["NCOR"] = _safe_int(_read_value(line))

        # NTIP
        line = _next_line()
        if line is None:
            return result
        result["NTIP"] = _safe_int(_read_value(line))

        # NWS
        line = _next_line()
        if line is None:
            return result
        result["NWS"] = _safe_int(_read_value(line))

        # NRAMP
        line = _next_line()
        if line is None:
            return result
        result["NRAMP"] = _safe_int(_read_value(line))

        # G
        line = _next_line()
        if line is None:
            return result
        result["G"] = _safe_float(_read_value(line))

        # TAU0 (may have additional values if -5)
        line = _next_line()
        if line is None:
            return result
        tau_parts = _read_value(line).split()
        result["TAU0"] = float(tau_parts[0]) if tau_parts else 0.0
        if len(tau_parts) >= 3 and result["TAU0"] == -5.0:
            result["TAU0_FullDomainMin"] = float(tau_parts[1])
            result["TAU0_FullDomainMax"] = float(tau_parts[2])

        # DTDP
        line = _next_line()
        if line is None:
            return result
        result["DTDP"] = _safe_float(_read_value(line))

        # STATIM
        line = _next_line()
        if line is None:
            return result
        result["STATIM"] = _safe_float(_read_value(line))

        # REFTIM
        line = _next_line()
        if line is None:
            return result
        result["REFTIM"] = _safe_float(_read_value(line))

        # RNDAY
        line = _next_line()
        if line is None:
            return result
        result["RNDAY"] = _safe_float(_read_value(line))

        # DRAMP (may have additional values for NRAMP > 1)
        line = _next_line()
        if line is None:
            return result
        dramp_parts = _read_value(line).split()
        result["DRAMP"] = float(dramp_parts[0]) if dramp_parts else 0.0

        # A00 B00 C00 (time weighting factors)
        line = _next_line()
        if line is None:
            return result
        abc_parts = _read_value(line).split()
        if len(abc_parts) >= 3:
            result["A00"] = float(abc_parts[0])
            result["B00"] = float(abc_parts[1])
            result["C00"] = float(abc_parts[2])

        # H0 (may include NODEDRYMIN NODEWETMIN VELMIN)
        line = _next_line()
        if line is None:
            return result
        h0_parts = _read_value(line).split()
        result["H0"] = float(h0_parts[0]) if h0_parts else 0.0
        if len(h0_parts) >= 3:
            result["NODEDRYMIN"] = float(h0_parts[1])
            result["NODEWETMIN"] = float(h0_parts[2])
        if len(h0_parts) >= 4:
            result["VELMIN"] = float(h0_parts[3])

        # SLAM0 SFEA0
        line = _next_line()
        if line is None:
            return result
        slam_parts = _read_value(line).split()
        if len(slam_parts) >= 2:
            result["SLAM0"] = float(slam_parts[0])
            result["SFEA0"] = float(slam_parts[1])

        # Friction parameters depend on NOLIBF
        line = _next_line()
        if line is None:
            return result
        if result.get("NOLIBF", 0) in (0, 1):
            result["CF"] = _safe_float(_read_value(line))
        else:
            cf_parts = _read_value(line).split()
            result["CF"] = float(cf_parts[0]) if cf_parts else 0.0
            if len(cf_parts) >= 4:
                result["HBREAK"] = float(cf_parts[1])
                result["FTHETA"] = float(cf_parts[2])
                result["FGAMMA"] = float(cf_parts[3])

        # ESLM
        line = _next_line()
        if line is None:
            return result
        result["ESLM"] = _safe_float(_read_value(line))

        # CORI
        line = _next_line()
        if line is None:
            return result
        result["CORI"] = _safe_float(_read_value(line))

        # NTIF
        line = _next_line()
        if line is None:
            return result
        result["NTIF"] = _safe_int(_read_value(line))

        # Tidal potential constituents
        result["tidal_potential"] = []
        for _ in range(result["NTIF"]):
            const_name = _next_line()
            const_vals = _next_line()
            if const_name and const_vals:
                parts = _read_value(const_vals).split()
                entry = {"name": const_name.strip()}
                if len(parts) >= 5:
                    entry["TPK"] = float(parts[0])
                    entry["AMIGT"] = float(parts[1])
                    entry["ETRF"] = float(parts[2])
                    entry["FFT"] = float(parts[3])
                    entry["FACET"] = float(parts[4])
                result["tidal_potential"].append(entry)

        # NBFR
        line = _next_line()
        if line is None:
            return result
        result["NBFR"] = _safe_int(_read_value(line))

        # Boundary forcing frequencies
        result["boundary_forcing"] = []
        for _ in range(result["NBFR"]):
            const_name = _next_line()
            const_vals = _next_line()
            if const_name and const_vals:
                parts = _read_value(const_vals).split()
                entry = {"name": const_name.strip()}
                if len(parts) >= 3:
                    entry["AMIG"] = float(parts[0])
                    entry["FF"] = float(parts[1])
                    entry["FACE"] = float(parts[2])
                result["boundary_forcing"].append(entry)

        # ANGINN
        line = _next_line()
        if line is None:
            return result
        result["ANGINN"] = _safe_float(_read_value(line))

        # Continue parsing output sections...
        # The remaining sections are highly variable. We parse what we can.

        # Try to find output parameters
        # NOUTE TOUTSE TOUTFE NSPOOLE
        line = _next_line()
        if line is not None:
            out_parts = _read_value(line).split()
            if len(out_parts) >= 4:
                result["NOUTE"] = int(out_parts[0])
                result["TOUTSE"] = float(out_parts[1])
                result["TOUTFE"] = float(out_parts[2])
                result["NSPOOLE"] = int(out_parts[3])

            # NSTAE
            line = _next_line()
            if line is not None:
                result["NSTAE"] = _safe_int(_read_value(line))

                # Station coordinates
                result["elevation_stations"] = []
                for _ in range(result.get("NSTAE", 0)):
                    stn_line = _next_line()
                    if stn_line:
                        stn_parts = _read_value(stn_line).split()
                        if len(stn_parts) >= 2:
                            result["elevation_stations"].append(
                                {"x": float(stn_parts[0]), "y": float(stn_parts[1])}
                            )

    except Exception as e:
        result["_warnings"].append(f"Parser stopped at line {i}: {e}")

    result["_parsed_lines"] = i
    return result


def parse_fort14_header(text: str) -> dict:
    """Parse fort.14 (ADCIRC mesh) header.

    Only reads the first few lines for metadata — does NOT load full mesh.
    Returns grid name, node count, element count.
    """
    lines = text.strip().splitlines()
    result: dict = {}

    if len(lines) < 2:
        return {"error": "File too short to be a valid fort.14"}

    result["grid_name"] = lines[0].strip()

    # Line 2: NE NP (elements, nodes)
    parts = lines[1].strip().split()
    if len(parts) >= 2:
        result["num_elements"] = int(parts[0])
        result["num_nodes"] = int(parts[1])
    else:
        return {"error": f"Cannot parse element/node counts from line 2: {lines[1]}"}

    # To find boundary info, we'd need to skip past all nodes and elements.
    # For header-only parsing, just report the counts.
    # Boundary info would start at line 2 + NP + NE + 1
    np_count = result.get("num_nodes", 0)
    ne_count = result.get("num_elements", 0)
    boundary_start = 2 + np_count + ne_count

    if len(lines) > boundary_start:
        try:
            result["num_open_boundaries"] = int(
                lines[boundary_start].strip().split()[0]
            )
            if len(lines) > boundary_start + 1:
                result["total_open_boundary_nodes"] = int(
                    lines[boundary_start + 1].strip().split()[0]
                )
        except (ValueError, IndexError):
            pass

    return result


def parse_fort13(text: str) -> dict:
    """Parse fort.13 (nodal attributes) file.

    Returns attribute names, default values, and non-default node counts.
    """
    lines = text.strip().splitlines()
    result: dict = {"attributes": []}

    if len(lines) < 3:
        return {"error": "File too short to be a valid fort.13"}

    result["grid_name"] = lines[0].strip()

    try:
        result["num_nodes"] = int(lines[1].strip())
    except ValueError:
        return {"error": f"Cannot parse node count from line 2: {lines[1]}"}

    try:
        num_attrs = int(lines[2].strip())
        result["num_attributes"] = num_attrs
    except ValueError:
        return {"error": f"Cannot parse attribute count from line 3: {lines[2]}"}

    # Parse attribute definitions
    i = 3
    for _ in range(num_attrs):
        if i >= len(lines):
            break
        attr: dict = {}
        attr["name"] = lines[i].strip()
        i += 1
        if i < len(lines):
            attr["units"] = lines[i].strip()
            i += 1
        if i < len(lines):
            attr["values_per_node"] = int(lines[i].strip().split()[0])
            i += 1
        if i < len(lines):
            attr["default_values"] = lines[i].strip()
            i += 1
        result["attributes"].append(attr)

    # After attribute definitions, parse non-default assignments
    for attr in result["attributes"]:
        if i >= len(lines):
            break
        # Attribute name line (skip)
        i += 1
        # Number of non-default nodes
        if i < len(lines):
            try:
                num_nondefault = int(lines[i].strip().split()[0])
                attr["num_nondefault_nodes"] = num_nondefault
                i += 1
                # Skip the actual non-default node lines
                i += num_nondefault
            except ValueError:
                attr["num_nondefault_nodes"] = 0

    return result


def parse_fort22_header(text: str, nws: int = 0) -> dict:
    """Parse fort.22 meteorological forcing file header.

    The format depends on the NWS value.
    Returns format type, time range, and spatial extent if available.
    """
    lines = text.strip().splitlines()
    result: dict = {"nws": nws, "num_lines": len(lines)}

    if not lines:
        return {"error": "Empty fort.22 file"}

    if abs(nws) in (8, 9, 16, 19, 20):
        # ATCF best-track format (or variants)
        result["format"] = "ATCF_best_track"
        result["num_records"] = len(lines)
        # Try to parse first and last line for time range
        first_parts = lines[0].split(",")
        last_parts = lines[-1].split(",")
        if len(first_parts) >= 3:
            result["first_timestamp"] = first_parts[2].strip()
        if len(last_parts) >= 3:
            result["last_timestamp"] = last_parts[2].strip()

    elif abs(nws) in (5, 6, 10, 12):
        # OWI format - header lines describe grid
        result["format"] = "OWI_gridded"
        if lines:
            result["header_line"] = lines[0].strip()

    elif abs(nws) in (1, 2):
        # Simple uniform wind format
        result["format"] = "uniform_wind"
        result["num_records"] = len(lines)

    else:
        result["format"] = "unknown"
        result["first_line"] = lines[0].strip() if lines else ""

    return result


def validate_fort15(
    parsed: dict,
    fort14_info: dict | None = None,
    fort13_info: dict | None = None,
) -> list[dict]:
    """Validate a parsed fort.15 configuration.

    Returns a list of issues with severity ('error', 'warning', 'info') and suggested fixes.
    """
    issues: list[dict] = []

    # Check CFL condition if we have DTDP
    dtdp = parsed.get("DTDP", 0)
    if dtdp <= 0:
        issues.append(
            {
                "severity": "error",
                "parameter": "DTDP",
                "message": f"Invalid timestep DTDP={dtdp}. Must be positive.",
                "fix": "Set DTDP to a positive value (typically 0.5-60 seconds).",
            }
        )

    # Check RNDAY
    rnday = parsed.get("RNDAY", 0)
    if rnday <= 0:
        issues.append(
            {
                "severity": "error",
                "parameter": "RNDAY",
                "message": f"Invalid run duration RNDAY={rnday}. Must be positive.",
                "fix": "Set RNDAY to the desired simulation duration in days.",
            }
        )

    # Check DRAMP
    dramp = parsed.get("DRAMP", 0)
    nramp = parsed.get("NRAMP", 0)
    if nramp > 0 and dramp <= 0:
        issues.append(
            {
                "severity": "warning",
                "parameter": "DRAMP",
                "message": "NRAMP > 0 but DRAMP <= 0. Ramp is enabled but has zero duration.",
                "fix": "Set DRAMP to at least 1.0 day for tidal runs.",
            }
        )
    elif dramp > 0 and dramp < 0.5:
        issues.append(
            {
                "severity": "warning",
                "parameter": "DRAMP",
                "message": f"DRAMP={dramp} days is very short. May cause instability.",
                "fix": "Increase DRAMP to at least 0.5-1.0 days.",
            }
        )

    # Check NWS and companion files
    nws = parsed.get("NWS", 0)
    from .models import NWS_VALUES

    if nws != 0 and nws not in NWS_VALUES:
        issues.append(
            {
                "severity": "warning",
                "parameter": "NWS",
                "message": f"NWS={nws} is not a commonly used value.",
                "fix": "Verify NWS value. Common values: 0, 8, 12, -12, 16.",
            }
        )

    # Check IHOT and STATIM consistency
    ihot = parsed.get("IHOT", 0)
    statim = parsed.get("STATIM", 0)
    if ihot == 0 and statim != 0:
        issues.append(
            {
                "severity": "warning",
                "parameter": "STATIM",
                "message": f"Cold start (IHOT=0) but STATIM={statim}. STATIM is usually 0 for cold starts.",
                "fix": "Set STATIM=0 for cold start runs.",
            }
        )

    # Check ICS and coordinate values
    ics = parsed.get("ICS", 1)
    slam0 = parsed.get("SLAM0", 0)
    sfea0 = parsed.get("SFEA0", 0)
    if ics == 2 and slam0 == 0 and sfea0 == 0:
        issues.append(
            {
                "severity": "warning",
                "parameter": "SLAM0/SFEA0",
                "message": "Spherical coordinates (ICS=2) but SLAM0=SFEA0=0. Projection center should match domain.",
                "fix": "Set SLAM0 and SFEA0 to the center of your mesh domain.",
            }
        )

    # Check NOLIBF consistency
    nolibf = parsed.get("NOLIBF", 0)
    nwp = parsed.get("NWP", 0)
    attrs = parsed.get("nodal_attributes", [])
    if nolibf == 2 and "mannings_n_at_sea_floor" not in attrs and nwp > 0:
        issues.append(
            {
                "severity": "warning",
                "parameter": "NOLIBF",
                "message": "NOLIBF=2 (spatially varying friction) but mannings_n_at_sea_floor not in nodal attributes.",
                "fix": "Add mannings_n_at_sea_floor to fort.13 or change NOLIBF to 1.",
            }
        )

    # Check wetting/drying settings
    nolifa = parsed.get("NOLIFA", 0)
    h0 = parsed.get("H0", 0)
    if nolifa == 2 and h0 <= 0:
        issues.append(
            {
                "severity": "error",
                "parameter": "H0",
                "message": f"Wetting/drying enabled (NOLIFA=2) but H0={h0}. H0 must be positive.",
                "fix": "Set H0 to a small positive value (typically 0.01-0.1 meters).",
            }
        )

    # Check time weighting
    a00 = parsed.get("A00", 0)
    b00 = parsed.get("B00", 0)
    c00 = parsed.get("C00", 0)
    if a00 + b00 + c00 > 0 and abs(a00 + b00 + c00 - 1.0) > 0.01:
        issues.append(
            {
                "severity": "warning",
                "parameter": "A00/B00/C00",
                "message": f"Time weighting factors A00+B00+C00={a00 + b00 + c00:.3f}, should sum to 1.0.",
                "fix": "Typical values: A00=0.35, B00=0.30, C00=0.35.",
            }
        )

    # Check NTIF/NBFR consistency
    ntif = parsed.get("NTIF", 0)
    nbfr = parsed.get("NBFR", 0)
    tidal_potential = parsed.get("tidal_potential", [])
    boundary_forcing = parsed.get("boundary_forcing", [])
    if ntif != len(tidal_potential):
        issues.append(
            {
                "severity": "error",
                "parameter": "NTIF",
                "message": f"NTIF={ntif} but found {len(tidal_potential)} tidal potential constituents.",
                "fix": "Ensure NTIF matches the number of tidal potential constituent entries.",
            }
        )
    if nbfr != len(boundary_forcing):
        issues.append(
            {
                "severity": "error",
                "parameter": "NBFR",
                "message": f"NBFR={nbfr} but found {len(boundary_forcing)} boundary forcing constituents.",
                "fix": "Ensure NBFR matches the number of boundary forcing frequency entries.",
            }
        )

    # Cross-reference with fort.14
    if fort14_info:
        # Check node count consistency
        if fort13_info and "num_nodes" in fort14_info and "num_nodes" in fort13_info:
            if fort14_info["num_nodes"] != fort13_info["num_nodes"]:
                issues.append(
                    {
                        "severity": "error",
                        "parameter": "fort.13/fort.14",
                        "message": (
                            f"Node count mismatch: fort.14 has {fort14_info['num_nodes']} nodes, "
                            f"fort.13 has {fort13_info['num_nodes']} nodes."
                        ),
                        "fix": "Regenerate fort.13 for the current mesh.",
                    }
                )

    # Cross-reference with fort.13
    if fort13_info:
        if nwp != fort13_info.get("num_attributes", 0):
            issues.append(
                {
                    "severity": "error",
                    "parameter": "NWP",
                    "message": (
                        f"NWP={nwp} in fort.15 but fort.13 has "
                        f"{fort13_info.get('num_attributes', 0)} attributes."
                    ),
                    "fix": "Ensure NWP matches the number of attributes in fort.13.",
                }
            )

    return issues


def check_cfl(dtdp: float, min_edge_length: float, max_depth: float) -> dict:
    """Check the CFL condition for ADCIRC.

    CFL criterion: DTDP < dx_min / sqrt(g * h_max)

    Args:
        dtdp: Time step in seconds.
        min_edge_length: Minimum element edge length in meters.
        max_depth: Maximum water depth in meters.

    Returns:
        Dict with CFL number, limit, and pass/fail status.
    """
    g = 9.81
    if max_depth <= 0:
        return {"error": "max_depth must be positive"}
    if min_edge_length <= 0:
        return {"error": "min_edge_length must be positive"}

    wave_speed = math.sqrt(g * max_depth)
    cfl_limit = min_edge_length / wave_speed
    cfl_number = dtdp / cfl_limit

    return {
        "dtdp": dtdp,
        "min_edge_length": min_edge_length,
        "max_depth": max_depth,
        "wave_speed": round(wave_speed, 2),
        "cfl_limit": round(cfl_limit, 4),
        "cfl_number": round(cfl_number, 4),
        "passes": cfl_number < 1.0,
        "recommendation": (
            f"CFL={cfl_number:.4f} — OK. Timestep {dtdp}s is within the CFL limit of {cfl_limit:.2f}s."
            if cfl_number < 1.0
            else f"CFL={cfl_number:.4f} — VIOLATION! Reduce DTDP below {cfl_limit:.2f}s or coarsen the mesh."
        ),
    }


def match_error_pattern(text: str) -> list[dict]:
    """Match error text against known ADCIRC failure patterns.

    Returns matching patterns with diagnosis and suggested fixes.
    """
    from .models import ADCIRC_ERROR_PATTERNS

    text_lower = text.lower()
    matches = []

    for pattern in ADCIRC_ERROR_PATTERNS:
        if any(kw.lower() in text_lower for kw in pattern["keywords"]):
            matches.append(
                {
                    "diagnosis": pattern["diagnosis"],
                    "fixes": pattern["fixes"],
                    "matched_keywords": [
                        kw for kw in pattern["keywords"] if kw.lower() in text_lower
                    ],
                }
            )

    return matches
