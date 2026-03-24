"""Tools for managing CORAL threshold alerts on NOAA CO-OPS stations."""

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations

from ..alert_manager import AlertError, AlertManager
from ..server import mcp


def _get_manager(ctx: Context) -> AlertManager:
    return ctx.request_context.lifespan_context["alert_manager"]


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=True,
    )
)
async def coral_create_alert(
    ctx: Context,
    station_id: str,
    operator: str,
    threshold: float,
    product: str = "water_level",
    interval_minutes: int = 5,
) -> str:
    """Create a new threshold alert for a NOAA CO-OPS station.

    Monitors the latest value for the given product and triggers when the
    value crosses the threshold according to the operator.

    Args:
        station_id: NOAA CO-OPS station ID (e.g. '8518750' for The Battery).
        operator: Comparison operator — one of >, <, >=, <=.
        threshold: Numeric threshold value (metric units, MLLW datum).
        product: CO-OPS data product to monitor (default: 'water_level').
        interval_minutes: Check interval in minutes (default: 5).
    """
    manager = _get_manager(ctx)
    try:
        alert = manager.create_alert(
            station_id=station_id,
            product=product,
            operator=operator,
            threshold=threshold,
            interval_seconds=interval_minutes * 60,
        )
    except AlertError as e:
        return f"**Error:** {e}"

    return (
        f"## Alert Created\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **ID** | `{alert['id']}` |\n"
        f"| **Station** | {alert['station_id']} |\n"
        f"| **Product** | {alert['product']} |\n"
        f"| **Condition** | value {alert['operator']} {alert['threshold']} |\n"
        f"| **Interval** | {interval_minutes} min |\n"
        f"| **Status** | Active |\n"
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def coral_list_alerts(ctx: Context) -> str:
    """List all active and paused threshold alerts.

    Shows each alert's ID, station, condition, status, and last checked value.
    """
    manager = _get_manager(ctx)
    alerts = manager.list_alerts()

    if not alerts:
        return "No alerts configured."

    lines = ["## Threshold Alerts\n"]
    lines.append("| ID | Station | Product | Condition | Status | Last Value |")
    lines.append("|----|---------|---------|-----------| -------|------------|")

    for a in alerts:
        status = "Active" if a["active"] else "Paused"
        last_val = f"{a['last_value']}" if a["last_value"] is not None else "—"
        lines.append(
            f"| `{a['id']}` | {a['station_id']} | {a['product']} "
            f"| {a['operator']} {a['threshold']} | {status} | {last_val} |"
        )

    return "\n".join(lines)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def coral_check_alerts(ctx: Context) -> str:
    """Manually trigger a check cycle on all active alerts.

    Fetches the latest value from NOAA CO-OPS for each active alert and
    evaluates the threshold condition. Returns the status of each alert.
    """
    manager = _get_manager(ctx)
    results = await manager.check_all_alerts()

    if not results:
        return "No active alerts to check."

    lines = ["## Alert Check Results\n"]
    for r in results:
        icon = "TRIGGERED" if r["triggered"] else "OK"
        lines.append(f"- **[{icon}]** `{r['alert_id']}`: {r['message']}")

    return "\n".join(lines)


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def coral_pause_alert(ctx: Context, alert_id: str) -> str:
    """Pause an active alert so it is skipped during check cycles.

    Args:
        alert_id: The alert ID to pause.
    """
    manager = _get_manager(ctx)
    try:
        alert = manager.pause_alert(alert_id)
    except AlertError as e:
        return f"**Error:** {e}"

    return (
        f"Alert `{alert['id']}` for station {alert['station_id']} "
        f"({alert['operator']} {alert['threshold']}) is now **paused**."
    )


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def coral_delete_alert(ctx: Context, alert_id: str) -> str:
    """Delete a threshold alert permanently.

    Args:
        alert_id: The alert ID to delete.
    """
    manager = _get_manager(ctx)
    try:
        manager.delete_alert(alert_id)
    except AlertError as e:
        return f"**Error:** {e}"

    return f"Alert `{alert_id}` deleted."


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def coral_get_alert_history(ctx: Context, alert_id: str) -> str:
    """Show trigger history for a threshold alert.

    Returns a list of timestamps and values for every time the alert
    condition was met.

    Args:
        alert_id: The alert ID to query.
    """
    manager = _get_manager(ctx)
    try:
        history = manager.get_alert_history(alert_id)
    except AlertError as e:
        return f"**Error:** {e}"

    if not history:
        return f"No trigger history for alert `{alert_id}`."

    lines = [f"## Trigger History for `{alert_id}`\n"]
    lines.append("| # | Timestamp | Value |")
    lines.append("|---|-----------|-------|")

    for i, entry in enumerate(history, 1):
        lines.append(f"| {i} | {entry['timestamp']} | {entry['value']} |")

    return "\n".join(lines)
