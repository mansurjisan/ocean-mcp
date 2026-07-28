"""Shared JSON response wrapper for winds-mcp tools.

Every JSON-emitting tool routes its payload through wrap_json() so the
response carries retrieved_at plus a {truncated, returned, total, hint}
envelope around the (possibly capped) data — per CONVENTIONS.md "Output
caps" and "JSON response wrappers". This module is local to winds-mcp only
(CONVENTIONS.md's "no shared runtime package" is about cross-server
sharing, not intra-server); it is used by both tools/stations.py and
tools/observations.py so the two don't drift into different envelope
shapes.
"""

import json
from datetime import datetime, timezone
from typing import Any, Literal


def wrap_json(
    data: Any,
    *,
    list_key: str | None,
    max_records: int = 2000,
    keep: Literal["head", "tail"] = "head",
    recent: bool = True,
    **context: Any,
) -> str:
    """Wrap a payload with retrieved_at and a truncation envelope.

    Args:
        data: The upstream/derived payload to wrap (typically a dict).
        list_key: Key in ``data`` holding the record list to cap (e.g.
            "features", "results", "summaries"). Pass None for a
            single-object payload with nothing to trim.
        max_records: Cap applied to the list at ``list_key``.
        keep: Which end of an over-cap list survives — "head" for
            newest-first sources (e.g. NWS observations), "tail" for
            oldest-first sources (e.g. the IEM ASOS archive). See
            CONVENTIONS.md "Output caps": oldest-first sources keep the
            tail (most recent), newest-first sources keep the head.
        recent: Whether the kept end is chronologically the most recent
            data (controls the truncation hint's wording — "most recent"
            vs "first" for order-unspecified lists like station listings).
        **context: Request-context fields (station id, params, ...)
            carried at the top level alongside the envelope.

    Returns:
        A JSON string: the context fields, then truncated/returned/total/
        retrieved_at/hint(if truncated), then the (possibly capped) data.
    """
    if (
        list_key is not None
        and isinstance(data, dict)
        and isinstance(data.get(list_key), list)
    ):
        records = data[list_key]
        total = len(records)
        truncated = total > max_records
        if truncated:
            kept = records[:max_records] if keep == "head" else records[-max_records:]
            data = {**data, list_key: kept}
        else:
            kept = records
        returned = len(kept)
    else:
        total = returned = 1
        truncated = False

    out: dict[str, Any] = dict(context)
    out["truncated"] = truncated
    out["returned"] = returned
    out["total"] = total
    out["retrieved_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    if truncated:
        which = "most recent" if recent else "first"
        out["hint"] = (
            f"Showing the {which} {returned} of {total} records. Narrow the "
            "request, or raise max_records, to see more."
        )
    out["data"] = data
    return json.dumps(out, indent=2)
