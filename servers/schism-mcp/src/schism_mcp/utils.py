"""Core parsers for SCHISM input files."""

from __future__ import annotations

import re


def parse_param_nml(text: str) -> dict:
    """Parse a SCHISM param.nml FORTRAN namelist file.

    Handles:
    - &SECTION ... / blocks
    - ! comments
    - .true. / .false. booleans
    - Quoted strings
    - Array values (e.g., iof_hydro(1) = 1)
    - Multiple values on one line (comma or space separated)
    """
    result: dict = {"_sections": {}}
    current_section = None

    for line in text.splitlines():
        stripped = line.strip()

        # Skip empty lines and pure comments
        if not stripped or stripped.startswith("!"):
            continue

        # Section start: &CORE, &OPT, &SCHOUT, etc.
        section_match = re.match(r"&(\w+)", stripped)
        if section_match:
            current_section = section_match.group(1).upper()
            result["_sections"][current_section] = {}
            continue

        # Section end: /
        if stripped == "/" or stripped == "&end":
            current_section = None
            continue

        if current_section is None:
            continue

        # Remove inline comments
        comment_idx = _find_comment_position(stripped)
        if comment_idx >= 0:
            stripped = stripped[:comment_idx].strip()

        if not stripped:
            continue

        # Parse key = value pairs
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip().lower()
            value = value.strip().rstrip(",")

            # Parse the value
            parsed_value = _parse_value(value)
            result["_sections"][current_section][key] = parsed_value
            result[key] = parsed_value

    return result


def _find_comment_position(line: str) -> int:
    """Find the position of a comment character (!) not inside quotes."""
    in_quote = False
    quote_char = ""
    for i, ch in enumerate(line):
        if ch in ('"', "'") and not in_quote:
            in_quote = True
            quote_char = ch
        elif ch == quote_char and in_quote:
            in_quote = False
        elif ch == "!" and not in_quote:
            return i
    return -1


def _parse_value(value: str) -> int | float | bool | str:
    """Parse a FORTRAN namelist value."""
    value = value.strip()

    # Boolean
    if value.lower() in (".true.", "t", ".t."):
        return True
    if value.lower() in (".false.", "f", ".f."):
        return False

    # Quoted string
    if (value.startswith("'") and value.endswith("'")) or (
        value.startswith('"') and value.endswith('"')
    ):
        return value[1:-1]

    # Integer
    try:
        return int(value)
    except ValueError:
        pass

    # Float (handle Fortran D/d notation)
    try:
        return float(value.replace("d", "e").replace("D", "E"))
    except ValueError:
        pass

    return value


def parse_hgrid_header(text: str) -> dict:
    """Parse hgrid.gr3 (SCHISM horizontal grid) header.

    Only reads the first few lines for metadata. Does NOT load full mesh.
    Returns node/element counts and bounding box if available.
    """
    lines = text.strip().splitlines()
    result: dict = {}

    if len(lines) < 2:
        return {"error": "File too short to be a valid hgrid.gr3"}

    result["grid_name"] = lines[0].strip()

    # Line 2: NE NP (elements, nodes)
    parts = lines[1].strip().split()
    if len(parts) >= 2:
        result["num_elements"] = int(parts[0])
        result["num_nodes"] = int(parts[1])
    else:
        return {"error": f"Cannot parse element/node counts from line 2: {lines[1]}"}

    # Try to compute bounding box from node coordinates
    # Nodes start at line 3: node_id x y depth
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    node_count = 0
    max_depth = 0.0

    for line_idx in range(2, min(len(lines), 2 + result["num_nodes"])):
        parts = lines[line_idx].strip().split()
        if len(parts) >= 4:
            try:
                x = float(parts[1])
                y = float(parts[2])
                depth = float(parts[3])
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
                max_depth = max(max_depth, abs(depth))
                node_count += 1
            except ValueError:
                break

    if node_count > 0:
        result["bounding_box"] = {
            "min_x": round(min_x, 6),
            "max_x": round(max_x, 6),
            "min_y": round(min_y, 6),
            "max_y": round(max_y, 6),
        }
        result["max_depth"] = round(max_depth, 2)
        result["nodes_scanned"] = node_count

    # Boundary info: after nodes and elements
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


def parse_vgrid(text: str) -> dict:
    """Parse vgrid.in (SCHISM vertical grid).

    Returns grid type (LSC2/SZ), number of levels, and layer distribution summary.
    """
    lines = text.strip().splitlines()
    result: dict = {}

    if not lines:
        return {"error": "Empty vgrid.in file"}

    # Line 1: ivcor (1=LSC2, 2=SZ)
    try:
        ivcor = int(lines[0].strip().split()[0])
        result["ivcor"] = ivcor
    except (ValueError, IndexError):
        return {
            "error": f"Cannot parse vertical coordinate type from line 1: {lines[0]}"
        }

    from .models import VGRID_TYPES

    if ivcor in VGRID_TYPES:
        result["type_name"] = VGRID_TYPES[ivcor]["name"]
        result["type_description"] = VGRID_TYPES[ivcor]["description"]

    if ivcor == 2:
        # SZ coordinates
        # Line 2: nvrt, kz (# of Z-levels), h_s (S-Z transition depth) — all
        # three values together on the same line. Verified against a real
        # SZ vgrid.in (servers/ufs-runner-mcp/.../schism_sandy_duck/vgrid.in),
        # e.g. "31 1 5000.    ! nvrt, kz (# of Z-levels); h_s (transition
        # depth between S and Z)". A previous version of this parser read
        # nvrt alone from line 2 and kz/h_s from line 3, which doesn't match
        # the real file format and silently dropped kz/h_s.
        if len(lines) >= 2:
            parts = lines[1].strip().split()
            if len(parts) >= 1:
                try:
                    result["nvrt"] = int(parts[0])
                except ValueError:
                    pass
            if len(parts) >= 3:
                try:
                    result["kz"] = int(parts[1])
                    result["h_s"] = float(parts[2])
                except ValueError:
                    pass

    elif ivcor == 1:
        # LSC2 coordinates
        # Line 2: nvrt
        if len(lines) >= 2:
            try:
                result["nvrt"] = int(lines[1].strip().split()[0])
            except (ValueError, IndexError):
                pass

    result["num_lines"] = len(lines)
    return result


def parse_bctides(text: str) -> dict:
    """Parse bctides.in (SCHISM tidal boundary conditions).

    File layout, per the authoritative pseudo-code on the SCHISM manual's
    bctides.in page (https://schism-dev.github.io/schism/master/input-output/bctides.html,
    verified live 2026-07) and cross-checked against a real sample file
    (servers/ufs-runner-mcp/.../schism_sandy_duck/bctides.in):

        line 1:  free-form header (start date/time; not machine-parsed)
        line 2:  ntip tip_dp   - # of earth tidal-potential constituents,
                                  cutoff depth for applying tidal potential
        ntip blocks (only present if ntip > 0), each exactly 2 lines:
            talpha(k)                              - constituent name
            jspc(k) tamp(k) tfreq(k) tnf(k) tear(k) - species #, amplitude,
                                                       angular frequency,
                                                       nodal factor, earth
                                                       equilibrium argument
        nbfr    - # of tidal boundary-forcing frequencies
        nbfr blocks, each exactly 2 lines:
            alpha(k)               - constituent name
            amig(k) ff(k) face(k)  - angular frequency, nodal factor, earth
                                      equilibrium argument
        nope    - # of open boundary segments
        nope blocks, each:
            nond iettype ifltype itetype isatype [itrtype ...] - node count
                              and B.C. type codes for this boundary segment
            a data payload whose shape depends on each type code above
                              (see _bctides_payload_line_count)

    A previous version of this parser treated line 2 as nbfr directly,
    skipping ntip/tip_dp entirely. That happened to produce the right nbfr
    for files where ntip==0 (nothing to skip), but it never advanced past
    the real nbfr line to reach nope, so num_open_boundaries came out wrong
    for every file — including the real sample above (ntip=0, nbfr=0,
    nope=1; the old code reported num_open_boundaries=0).

    A later version fixed that but still didn't skip each boundary
    segment's data payload correctly for every type code (see
    _bctides_payload_line_count's docstring) — it crashed on the
    canonical sample_inputs/bctides.in from the SCHISM repo, which uses
    ifltype=2 and isatype=1/2 and needs those payloads skipped to reach
    the next boundary header.

    Returns tidal-potential terms, tidal boundary-forcing constituents,
    boundary segment types, and node counts.
    """
    lines = text.strip().splitlines()
    result: dict = {"tidal_potential": [], "constituents": [], "boundaries": []}

    if len(lines) < 3:
        return {"error": "File too short to be a valid bctides.in"}

    i = 0

    # Line 1: free-form header (start date/time)
    result["header"] = lines[i].strip()
    i += 1

    # Line 2: ntip tip_dp (# of earth tidal-potential terms, cutoff depth)
    try:
        parts = lines[i].strip().split()
        ntip = int(parts[0])
        result["ntip"] = ntip
        if len(parts) >= 2:
            result["tip_dp"] = float(parts[1])
        i += 1
    except (ValueError, IndexError):
        return {"error": f"Cannot parse ntip/tip_dp from line: {lines[i]}"}

    # Read ntip tidal-potential constituent definitions (2 lines each: a
    # name line, then species/amplitude/frequency/nodal-factor/earth-arg).
    for _ in range(ntip):
        if i >= len(lines):
            break
        name = lines[i].strip()
        i += 1
        if i < len(lines):
            parts = lines[i].strip().split()
            entry: dict = {"name": name}
            if len(parts) >= 5:
                try:
                    entry["species"] = int(parts[0])
                    entry["amplitude"] = float(parts[1])
                    entry["frequency"] = float(parts[2])
                    entry["nodal_factor"] = float(parts[3])
                    entry["earth_equil_arg"] = float(parts[4])
                except ValueError:
                    pass
            result["tidal_potential"].append(entry)
            i += 1

    # nbfr (number of tidal frequencies for boundary forcing)
    try:
        nbfr = int(lines[i].strip().split()[0])
        result["nbfr"] = nbfr
        i += 1
    except (ValueError, IndexError):
        return {"error": f"Cannot parse number of frequencies from line: {lines[i]}"}

    # Read tidal constituent definitions
    for _ in range(nbfr):
        if i >= len(lines):
            break
        # Constituent name line
        name = lines[i].strip()
        i += 1
        # Frequency, nodal factor, earth equilibrium argument
        if i < len(lines):
            parts = lines[i].strip().split()
            entry = {"name": name}
            if len(parts) >= 3:
                try:
                    entry["frequency"] = float(parts[0])
                    entry["nodal_factor"] = float(parts[1])
                    entry["earth_equil_arg"] = float(parts[2])
                except ValueError:
                    pass
            result["constituents"].append(entry)
            i += 1

    # Number of open boundaries
    if i < len(lines):
        try:
            nope = int(lines[i].strip().split()[0])
            result["num_open_boundaries"] = nope
            i += 1
        except (ValueError, IndexError):
            pass

    # Parse open boundary segments
    for _ in range(result.get("num_open_boundaries", 0)):
        if i >= len(lines):
            break
        boundary: dict = {}
        # Boundary header: nond iettype ifltype itetype isatype [itrtype ...]
        parts = lines[i].strip().split()
        i += 1
        if len(parts) >= 1:
            boundary["num_nodes"] = int(parts[0])
        if len(parts) >= 2:
            boundary["elevation_type"] = int(parts[1])
        if len(parts) >= 3:
            boundary["flux_type"] = int(parts[2])
        if len(parts) >= 4:
            boundary["temperature_type"] = int(parts[3])
        if len(parts) >= 5:
            boundary["salinity_type"] = int(parts[4])

        nond = boundary.get("num_nodes", 0)

        # Skip the data payload (if any) that follows this boundary's
        # header before the next boundary header, per the pseudo-code on
        # https://schism-dev.github.io/schism/master/input-output/bctides.html
        # (verified live 2026-07). The payload for each of the four B.C.
        # types depends on that type's own code, not a single shared rule
        # for "tidal" boundaries — a previous version of this parser
        # applied the elevation/velocity tidal skip (nbfr constituent
        # blocks) uniformly to all four type keys, which is wrong for
        # temperature/salinity type 3 (a single tobc nudging-factor line,
        # not nbfr blocks) and didn't skip anything at all for iettype=2,
        # ifltype=2/-4/-1, or itetype/isatype=1/2/4 — so on a real file
        # using any of those (e.g. the canonical sample_inputs/bctides.in,
        # which uses ifltype=2 and isatype=1/2) it would read a payload
        # line as the next boundary's header and crash.
        for bc_family, type_code in (
            ("elevation", boundary.get("elevation_type", 0)),
            ("velocity", boundary.get("flux_type", 0)),
            ("temperature", boundary.get("temperature_type", 0)),
            ("salinity", boundary.get("salinity_type", 0)),
        ):
            skip = _bctides_payload_line_count(bc_family, type_code, nond, nbfr)
            i = min(i + skip, len(lines))

        # NOTE: if additional tracer-module flags (GEN, AGE, SED3D,
        # EcoSim, ICM, CoSiNE, FIB, TIMOR) are present after isatype on
        # the header line, their payloads are NOT skipped here. The docs
        # describe that structure only in prose ("similar to temperature
        # ... for all classes in 1 row") rather than as precise
        # pseudo-code, and the number of tracer modules/classes invoked
        # is determined by param.nml, not by bctides.in itself — so it
        # can't be derived from this file alone. Files with tracer-module
        # boundary data will still mis-skip past this point.
        result["boundaries"].append(boundary)

    return result


def _bctides_payload_line_count(
    bc_family: str, type_code: int, nond: int, nbfr: int
) -> int:
    """Return the number of bctides.in lines that follow an open boundary
    header for one B.C. family's type code.

    Per the pseudo-code on
    https://schism-dev.github.io/schism/master/input-output/bctides.html
    (verified live 2026-07):

    Elevation (iettype) / velocity (ifltype) share the same "tidal" shape
    for type 3/5: nbfr blocks, each an `alpha(k)` name line followed by
    `nond` lines of per-node amplitude/phase data (2 values/line for
    elevation, 4 for velocity — the line *count* is the same either way).
    Type 2 is one constant line (ethconst/vthconst). Types 0/1/4 need no
    payload (unspecified, or read from a separate .th/.th.nc file).
    Velocity additionally has:
      - ifltype == -4: one line of two relaxation constants (rel1 rel2).
      - ifltype == -1 (Flather): two per-node blocks with no header line
        of their own — `nond` lines of eta_m0(i), then `nond` lines of
        qthcon(1:Nz,i,j). (The docs show 'eta_mean'/'vn_mean' next to
        these blocks, but the page explicitly marks them "comment only",
        not literal data lines.)

    Temperature (itetype) and salinity (isatype) share one structure (the
    docs state salinity is "similar to temperature above"): type 0 needs
    nothing; types 1/3/4 need one nudging-factor line (tobc); type 2 needs
    a constant line (tthconst/sthconst) followed by the tobc line.
    """
    if bc_family in ("elevation", "velocity"):
        if type_code == 2:
            return 1
        if type_code in (3, 5):
            return nbfr * (1 + nond)
        if bc_family == "velocity":
            if type_code == -4:
                return 1
            if type_code == -1:
                return 2 * nond
        return 0
    # temperature / salinity
    if type_code == 2:
        return 2
    if type_code in (1, 3, 4):
        return 1
    return 0


def validate_param_nml(
    parsed: dict,
    hgrid_info: dict | None = None,
    vgrid_info: dict | None = None,
) -> list[dict]:
    """Validate a parsed param.nml configuration.

    Returns a list of issues with severity and suggested fixes.
    """
    issues: list[dict] = []

    # Check dt
    dt = parsed.get("dt")
    if dt is not None:
        if dt <= 0:
            issues.append(
                {
                    "severity": "error",
                    "parameter": "dt",
                    "message": f"Invalid timestep dt={dt}. Must be positive.",
                    "fix": "Set dt to a positive value (typically 60-200 seconds).",
                }
            )
        elif dt > 400:
            issues.append(
                {
                    "severity": "warning",
                    "parameter": "dt",
                    "message": f"dt={dt}s is unusually large. May cause instability.",
                    "fix": "Typical dt is 60-200s depending on grid resolution.",
                }
            )

    # Check rnday
    rnday = parsed.get("rnday")
    if rnday is not None and rnday <= 0:
        issues.append(
            {
                "severity": "error",
                "parameter": "rnday",
                "message": f"Invalid run duration rnday={rnday}. Must be positive.",
                "fix": "Set rnday to the desired simulation duration in days.",
            }
        )

    # Check nspool/ihfskip divisibility
    nspool = parsed.get("nspool")
    ihfskip = parsed.get("ihfskip")
    if nspool and ihfskip:
        if ihfskip % nspool != 0:
            issues.append(
                {
                    "severity": "error",
                    "parameter": "nspool/ihfskip",
                    "message": f"ihfskip ({ihfskip}) is not evenly divisible by nspool ({nspool}).",
                    "fix": f"Set ihfskip to a multiple of nspool. E.g., ihfskip={nspool * (ihfskip // nspool)}.",
                }
            )

    # Check 2D vs 3D consistency
    itur = parsed.get("itur", 0)
    nvrt = vgrid_info.get("nvrt", 0) if vgrid_info else 0
    if itur in (3, 4) and nvrt and nvrt <= 2:
        issues.append(
            {
                "severity": "error",
                "parameter": "itur",
                "message": f"3D turbulence model (itur={itur}) but vertical grid has only {nvrt} levels.",
                "fix": "Use itur=0 for 2D runs, or increase vertical resolution.",
            }
        )

    # Check ramp settings
    nramp = parsed.get("nramp", 0)
    dramp = parsed.get("dramp", 0)
    if nramp == 1 and dramp <= 0:
        issues.append(
            {
                "severity": "warning",
                "parameter": "dramp",
                "message": "Tidal ramp enabled (nramp=1) but dramp <= 0.",
                "fix": "Set dramp to at least 1.0 day for tidal runs.",
            }
        )

    # Check coordinate system
    ics = parsed.get("ics")
    slam0 = parsed.get("slam0", 0)
    sfea0 = parsed.get("sfea0", 0)
    if ics == 2 and slam0 == 0 and sfea0 == 0:
        issues.append(
            {
                "severity": "warning",
                "parameter": "slam0/sfea0",
                "message": "Spherical coordinates (ics=2) but slam0=sfea0=0. Projection center should match domain.",
                "fix": "Set slam0 and sfea0 to the center of your mesh domain.",
            }
        )

    # Check nhot
    nhot = parsed.get("nhot", 0)
    if nhot == 1:
        issues.append(
            {
                "severity": "info",
                "parameter": "nhot",
                "message": "Hot start enabled (nhot=1). Verify hotstart.nc exists and is compatible.",
                "fix": "Ensure hotstart.nc was generated with matching grid and parameters.",
            }
        )

    # Check wind forcing
    nws_val = parsed.get("nws", 0)
    wtiminc = parsed.get("wtiminc", 0)
    if nws_val > 0 and dt and wtiminc and wtiminc < dt:
        issues.append(
            {
                "severity": "warning",
                "parameter": "wtiminc",
                "message": f"wtiminc ({wtiminc}s) < dt ({dt}s). Wind timestep should be >= model timestep.",
                "fix": f"Set wtiminc >= {dt}.",
            }
        )

    # Check h0
    h0 = parsed.get("h0")
    if h0 is not None and h0 <= 0:
        issues.append(
            {
                "severity": "error",
                "parameter": "h0",
                "message": f"h0={h0} must be positive for wetting/drying.",
                "fix": "Set h0 to a small positive value (typically 0.01-0.5 meters).",
            }
        )

    return issues


def match_error_pattern(text: str) -> list[dict]:
    """Match error text against known SCHISM failure patterns."""
    from .models import SCHISM_ERROR_PATTERNS

    text_lower = text.lower()
    matches = []

    for pattern in SCHISM_ERROR_PATTERNS:
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
