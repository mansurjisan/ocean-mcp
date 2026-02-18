"""Utilities: ERDDAP JSON parsing, URL building, formatting, error handling."""

from __future__ import annotations

from urllib.parse import quote


def parse_erddap_json(data: dict) -> list[dict]:
    """Convert ERDDAP JSON response into a list of row dicts.

    ERDDAP returns: {"table": {"columnNames": [...], "rows": [...]}}
    This converts it to: [{"col1": val1, "col2": val2}, ...]
    """
    table = data.get("table", {})
    columns = table.get("columnNames", [])
    rows = table.get("rows", [])

    return [dict(zip(columns, row)) for row in rows]


def format_erddap_table(
    rows: list[dict],
    columns: list[str] | None = None,
    title: str = "",
    metadata_lines: list[str] | None = None,
    count_label: str = "records",
    max_rows: int | None = None,
) -> str:
    """Format ERDDAP row dicts as a markdown table.

    Args:
        rows: List of row dicts.
        columns: Column names to display (default: all from first row).
        title: Optional markdown heading.
        metadata_lines: Optional metadata lines shown below the title.
        count_label: Label for the count footer.
        max_rows: Maximum rows to display (shows a note if truncated).
    """
    if not rows:
        header = f"## {title}\n\n" if title else ""
        return f"{header}No {count_label} found."

    if columns is None:
        columns = list(rows[0].keys())

    total = len(rows)
    if max_rows and len(rows) > max_rows:
        rows = rows[:max_rows]

    lines: list[str] = []

    if title:
        lines.append(f"## {title}")

    if metadata_lines:
        lines.append(" | ".join(f"**{m}**" for m in metadata_lines))
        lines.append("")

    # Header
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")

    # Rows
    for row in rows:
        cells = []
        for col in columns:
            val = row.get(col, "")
            cell = str(val) if val is not None else ""
            # Truncate long cell values
            if len(cell) > 100:
                cell = cell[:97] + "..."
            cells.append(cell)
        lines.append("| " + " | ".join(cells) + " |")

    lines.append("")
    if max_rows and total > max_rows:
        lines.append(f"*Showing {len(rows)} of {total} {count_label}. Use limit/offset for more.*")
    else:
        lines.append(f"*{total} {count_label} returned.*")

    return "\n".join(lines)


def build_tabledap_query(
    variables: list[str] | None = None,
    constraints: dict[str, str | int | float] | None = None,
    limit: int | None = None,
) -> str:
    """Build a tabledap URL query string.

    Args:
        variables: List of variable names to request.
        constraints: Dict of constraints, e.g. {"time>=": "2024-01-01", "latitude>=": 38.0}
        limit: Row limit (appended as orderByLimit constraint).

    Returns:
        Query string (without leading '?').
    """
    parts: list[str] = []

    # Variables
    if variables:
        parts.append(",".join(variables))

    # Constraints
    if constraints:
        for key, value in constraints.items():
            if isinstance(value, (int, float)):
                # Numeric values never need quoting
                parts.append(f"{key}{value}")
            else:
                # String values: determine if quoting is needed
                str_value = str(value)
                has_range_op = any(op in key for op in [">=", "<=", ">", "<", "!=", "=~"])

                if not has_range_op:
                    # Equality (key ends with "=" or has no operator) — always quote
                    parts.append(f'{key}"{str_value}"')
                else:
                    # Range operator — quote non-numeric values (dates, strings)
                    try:
                        float(str_value)
                        parts.append(f"{key}{str_value}")
                    except ValueError:
                        parts.append(f'{key}"{str_value}"')

    # Limit via orderByLimit
    if limit:
        parts.append(f"orderByLimit(\"{limit}\")")

    return "&".join(parts)


def build_griddap_query(
    variable: str,
    dimensions: dict[str, tuple[str, str] | tuple[str, str, str]],
) -> str:
    """Build a griddap URL query string with bracket notation.

    Args:
        variable: Variable name to request.
        dimensions: Ordered dict of dimension_name -> (start, stop) or (start, stride, stop).

    Returns:
        Query string (without leading '?'), e.g.:
        "sst[(2024-01-15T00:00:00Z)][(36):(38)][(-123):(-121)]"
    """
    parts = [variable]
    for dim_name, dim_range in dimensions.items():
        if len(dim_range) == 2:
            start, stop = dim_range
            if start == stop:
                parts.append(f"[({start})]")
            else:
                parts.append(f"[({start}):({stop})]")
        elif len(dim_range) == 3:
            start, stride, stop = dim_range
            parts.append(f"[({start}):({stride}):({stop})]")

    return "".join(parts)


def handle_erddap_error(e: Exception, server_url: str = "") -> str:
    """Format an ERDDAP error into a user-friendly message with suggestions.

    Args:
        e: The exception that occurred.
        server_url: The ERDDAP server URL that was being accessed.

    Returns:
        A formatted error message string.
    """
    import httpx

    msg = str(e)

    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        # Try to extract error message from HTML response
        body = ""
        try:
            body = e.response.text
        except Exception:
            pass

        if status == 404:
            suggestion = "The dataset may not exist on this server. Use erddap_search_datasets to find available datasets."
            if "info" in str(e.request.url):
                suggestion = "Dataset not found. Verify the dataset_id with erddap_search_datasets."
            return f"Error 404: Dataset or resource not found. {suggestion}"
        elif status == 500:
            # ERDDAP often returns 500 with useful error messages in HTML
            error_detail = _extract_html_error(body)
            suggestion = "Check your query constraints and variable names. Use erddap_get_dataset_info to see available variables and dimensions."
            return f"ERDDAP Server Error: {error_detail or 'Internal server error'}. {suggestion}"
        elif status == 408 or status == 504:
            return f"Error {status}: Request timed out. Try a smaller data subset (fewer time steps, smaller spatial area, or use stride > 1)."
        else:
            return f"HTTP Error {status}: {e.response.reason_phrase}. The ERDDAP server at {server_url} may be temporarily unavailable."

    if isinstance(e, httpx.TimeoutException):
        return f"Request timed out. ERDDAP servers can be slow for large queries. Try reducing your data request size or increasing stride."

    if isinstance(e, httpx.ConnectError):
        return f"Could not connect to ERDDAP server at {server_url}. The server may be down. Use erddap_list_servers to find alternative servers."

    if "json" in msg.lower() or "decode" in msg.lower():
        return f"Error parsing ERDDAP response (server may have returned HTML error). Check that dataset_id and variable names are correct. Use erddap_get_dataset_info to verify."

    return f"Unexpected error: {type(e).__name__}: {msg}"


def _extract_html_error(html: str) -> str:
    """Extract error message from ERDDAP HTML error response."""
    if not html:
        return ""

    # ERDDAP typically puts errors in specific patterns
    import re

    # Look for error messages in common ERDDAP patterns
    patterns = [
        r"<p[^>]*class=\"[^\"]*error[^\"]*\"[^>]*>(.*?)</p>",
        r"message=\"(.*?)\"",
        r"Error\s*\{[^}]*message\s*=\s*\"(.*?)\"",
        r"<title>(.*?)</title>",
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            text = match.group(1).strip()
            # Remove HTML tags
            text = re.sub(r"<[^>]+>", "", text)
            if text and len(text) < 500:
                return text

    return ""
