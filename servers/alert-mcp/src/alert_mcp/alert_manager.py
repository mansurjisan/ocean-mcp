"""Core alert management logic for CORAL threshold alerting."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

COOPS_API_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

VALID_OPERATORS = {">", "<", ">=", "<="}

_STATION_RE = re.compile(r"^[a-zA-Z0-9]+$")


def _compare(value: float, operator: str, threshold: float) -> bool:
    """Evaluate a threshold comparison."""
    if operator == ">":
        return value > threshold
    if operator == "<":
        return value < threshold
    if operator == ">=":
        return value >= threshold
    if operator == "<=":
        return value <= threshold
    return False


class AlertError(Exception):
    """Raised when an alert operation fails."""


class AlertManager:
    """Manages in-memory threshold alerts for NOAA CO-OPS stations."""

    def __init__(self) -> None:
        self._alerts: dict[str, dict[str, Any]] = {}

    def create_alert(
        self,
        station_id: str,
        product: str,
        operator: str,
        threshold: float,
        interval_seconds: int,
    ) -> dict[str, Any]:
        """Create a new threshold alert.

        Args:
            station_id: NOAA CO-OPS station identifier.
            product: CO-OPS data product (e.g. 'water_level').
            operator: Comparison operator (>, <, >=, <=).
            threshold: Threshold value for triggering.
            interval_seconds: Polling interval in seconds.

        Returns:
            The newly created alert dict.

        Raises:
            AlertError: If validation fails.
        """
        if operator not in VALID_OPERATORS:
            raise AlertError(
                f"Invalid operator '{operator}'. Must be one of: {', '.join(sorted(VALID_OPERATORS))}"
            )
        if not _STATION_RE.match(station_id):
            raise AlertError(
                f"Invalid station_id '{station_id}'. Must be alphanumeric."
            )

        alert_id = uuid.uuid4().hex[:8]
        now = datetime.now(timezone.utc).isoformat()

        alert: dict[str, Any] = {
            "id": alert_id,
            "station_id": station_id,
            "product": product,
            "operator": operator,
            "threshold": threshold,
            "interval_seconds": interval_seconds,
            "active": True,
            "created_at": now,
            "last_checked": None,
            "last_value": None,
            "triggered": False,
            "trigger_history": [],
        }
        self._alerts[alert_id] = alert
        return alert

    def list_alerts(self) -> list[dict[str, Any]]:
        """Return all alerts."""
        return list(self._alerts.values())

    async def check_alert(self, alert_id: str) -> dict[str, Any]:
        """Check a single alert by fetching the latest value from CO-OPS.

        Returns:
            A result dict with alert_id, value, triggered, and message.

        Raises:
            AlertError: If the alert does not exist.
        """
        alert = self._alerts.get(alert_id)
        if alert is None:
            raise AlertError(f"Alert '{alert_id}' not found.")

        now = datetime.now(timezone.utc).isoformat()
        alert["last_checked"] = now

        params = {
            "station": alert["station_id"],
            "product": alert["product"],
            "datum": "MLLW",
            "units": "metric",
            "time_zone": "gmt",
            "date": "latest",
            "format": "json",
            "application": "coral_alert",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(COOPS_API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            return {
                "alert_id": alert_id,
                "value": None,
                "triggered": False,
                "message": f"HTTP error fetching data: {exc}",
            }

        # Parse value from CO-OPS response
        try:
            records = data.get("data", [])
            if not records:
                return {
                    "alert_id": alert_id,
                    "value": None,
                    "triggered": False,
                    "message": "No data returned from CO-OPS API.",
                }
            value = float(records[-1]["v"])
        except (KeyError, ValueError, IndexError) as exc:
            return {
                "alert_id": alert_id,
                "value": None,
                "triggered": False,
                "message": f"Failed to parse CO-OPS response: {exc}",
            }

        alert["last_value"] = value
        triggered = _compare(value, alert["operator"], alert["threshold"])
        alert["triggered"] = triggered

        if triggered:
            alert["trigger_history"].append({"timestamp": now, "value": value})

        return {
            "alert_id": alert_id,
            "value": value,
            "triggered": triggered,
            "message": (
                f"TRIGGERED: {value} {alert['operator']} {alert['threshold']}"
                if triggered
                else f"OK: {value} does not satisfy {alert['operator']} {alert['threshold']}"
            ),
        }

    async def check_all_alerts(self) -> list[dict[str, Any]]:
        """Check all active alerts and return results."""
        results = []
        for alert_id, alert in self._alerts.items():
            if not alert["active"]:
                continue
            result = await self.check_alert(alert_id)
            results.append(result)
        return results

    def pause_alert(self, alert_id: str) -> dict[str, Any]:
        """Pause an alert.

        Raises:
            AlertError: If the alert does not exist.
        """
        alert = self._alerts.get(alert_id)
        if alert is None:
            raise AlertError(f"Alert '{alert_id}' not found.")
        alert["active"] = False
        return alert

    def resume_alert(self, alert_id: str) -> dict[str, Any]:
        """Resume a paused alert.

        Raises:
            AlertError: If the alert does not exist.
        """
        alert = self._alerts.get(alert_id)
        if alert is None:
            raise AlertError(f"Alert '{alert_id}' not found.")
        alert["active"] = True
        return alert

    def delete_alert(self, alert_id: str) -> None:
        """Delete an alert.

        Raises:
            AlertError: If the alert does not exist.
        """
        if alert_id not in self._alerts:
            raise AlertError(f"Alert '{alert_id}' not found.")
        del self._alerts[alert_id]

    def get_alert_history(self, alert_id: str) -> list[dict[str, Any]]:
        """Return the trigger history for an alert.

        Raises:
            AlertError: If the alert does not exist.
        """
        alert = self._alerts.get(alert_id)
        if alert is None:
            raise AlertError(f"Alert '{alert_id}' not found.")
        return list(alert["trigger_history"])
