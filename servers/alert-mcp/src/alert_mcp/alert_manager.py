"""Core alert management logic for CORAL threshold alerting."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from .client import AlertHTTPClient, CoopsAPIError

VALID_OPERATORS = {">", "<", ">=", "<="}

# Cap on how many trigger events an alert retains. This process holds alert
# state in memory for its entire lifetime with no eviction otherwise, so an
# alert left running for weeks/months would otherwise grow its history
# unbounded; 500 keeps a generous recent window without letting a
# long-running server's memory grow without limit.
MAX_TRIGGER_HISTORY = 500

_STATION_RE = re.compile(r"^[a-zA-Z0-9]+$")

# Per-product location of the record list and the field holding the
# comparable scalar within a CO-OPS datagetter JSON response. CO-OPS uses a
# different top-level key and per-record field depending on product — this
# was verified live against
# https://api.tidesandcurrents.noaa.gov/api/prod/datagetter and mirrors the
# same shape resolution coops_mcp.utils.format_json_response performs for
# the same upstream API:
#   water_level / most met products -> {"data": [{"v": ...}, ...]}
#   predictions (tide predictions)  -> {"predictions": [{"v": ...}, ...]}
#   wind / currents                 -> {"data": [{"s": ...}, ...]} (speed;
#                                       there is no "v" key on these records)
#   currents_predictions            -> {"current_predictions":
#                                        {"cp": [{"Velocity_Major": ...}]}}
#   one_minute_water_level / ofs_water_level -> {"data": [{"v": ...}, ...]}
#                                       (same shape as water_level, verified
#                                       live)
#
# check_alert always queries with "date": "latest" (see below), which rules
# out CO-OPS's archived/verified-data-only products regardless of their
# response shape: querying them with date=latest returns CO-OPS's HTTP-200
# error envelope ("No data was found...") at every station, every time, so
# an alert on one of them would always fail the create-time probe (or, pre
# this fix pass, silently never fire). Confirmed live for both
# "hourly_height" and "high_low" (across multiple stations) and for
# "daily_mean" (across multiple Great Lakes stations, and every date within
# roughly the last month — it only has data for older, fully-verified date
# ranges). All three are therefore deliberately left out of this map (as is
# "datums", which also isn't a single comparable time series in the same
# way). "air_gap" was
# checked the same way and does NOT have this problem — it returns live data
# via date=latest at any station that actually carries an air-gap sensor
# (e.g. station 8517986); it only errors at stations without the sensor,
# which is the correct, intended validation behavior.
_PRODUCT_VALUE_PATH: dict[str, tuple[tuple[str, ...], str]] = {
    "water_level": (("data",), "v"),
    "predictions": (("predictions",), "v"),
    "air_gap": (("data",), "v"),
    "air_pressure": (("data",), "v"),
    "air_temperature": (("data",), "v"),
    "water_temperature": (("data",), "v"),
    "humidity": (("data",), "v"),
    "conductivity": (("data",), "v"),
    "salinity": (("data",), "v"),
    "visibility": (("data",), "v"),
    "wind": (("data",), "s"),
    "currents": (("data",), "s"),
    "currents_predictions": (("current_predictions", "cp"), "Velocity_Major"),
    "one_minute_water_level": (("data",), "v"),
    "ofs_water_level": (("data",), "v"),
}

VALID_PRODUCTS = frozenset(_PRODUCT_VALUE_PATH)


def _get_records(data: dict, product: str) -> list:
    """Return the record list for ``product`` within a datagetter response."""
    path, _ = _PRODUCT_VALUE_PATH[product]
    node: Any = data
    for key in path:
        if not isinstance(node, dict):
            return []
        node = node.get(key)
    return node if isinstance(node, list) else []


def _extract_value(data: dict, product: str) -> float:
    """Extract the latest comparable scalar for ``product`` from a response.

    Raises:
        IndexError: If there are no records at all.
        KeyError: If the last record is missing the expected field.
        ValueError: If the field can't be converted to ``float``.
    """
    records = _get_records(data, product)
    if not records:
        raise IndexError("no records in CO-OPS response")
    _, value_key = _PRODUCT_VALUE_PATH[product]
    return float(records[-1][value_key])


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

    def __init__(self, client: AlertHTTPClient | None = None) -> None:
        self._alerts: dict[str, dict[str, Any]] = {}
        self._client = client or AlertHTTPClient()

    async def close(self) -> None:
        """Close the shared HTTP client. Call once at server shutdown."""
        await self._client.close()

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
        if product not in VALID_PRODUCTS:
            raise AlertError(
                f"Invalid product '{product}'. Must be one of: "
                f"{', '.join(sorted(VALID_PRODUCTS))}"
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
            A result dict with ``alert_id``, ``value``, ``triggered``,
            ``status``, and ``message``. ``status`` is one of:

            - ``"ok"``: a value was fetched and compared successfully.
            - ``"coops_error"``: CO-OPS returned its ``{"error": {...}}``
              envelope, on either HTTP 200 (e.g. a product this station
              doesn't currently support) or HTTP 400 (e.g. a bad
              station_id, or a product/station combination CO-OPS rejects
              outright) — the alert's configuration likely needs fixing.
            - ``"http_error"``: a transport failure, or a non-2xx HTTP
              status whose body wasn't CO-OPS's error-envelope shape.
            - ``"no_data"``: the request succeeded but returned no records.
            - ``"parse_error"``: a record was present but malformed.

        Raises:
            AlertError: If the alert does not exist.
        """
        alert = self._alerts.get(alert_id)
        if alert is None:
            raise AlertError(f"Alert '{alert_id}' not found.")

        now = datetime.now(timezone.utc).isoformat()
        alert["last_checked"] = now
        product = alert["product"]

        params = {
            "station": alert["station_id"],
            "product": product,
            "datum": "MLLW",
            "units": "metric",
            "time_zone": "gmt",
            "date": "latest",
        }

        try:
            data = await self._client.fetch(params)
        except CoopsAPIError as exc:
            return {
                "alert_id": alert_id,
                "value": None,
                "triggered": False,
                "status": "coops_error",
                "message": (
                    f"CO-OPS API error: {exc}. This alert's station_id/product "
                    "combination may be invalid — verify the station supports "
                    "this product, or delete and recreate the alert."
                ),
            }
        except httpx.HTTPError as exc:
            return {
                "alert_id": alert_id,
                "value": None,
                "triggered": False,
                "status": "http_error",
                "message": f"HTTP error fetching data: {exc}",
            }

        try:
            value = _extract_value(data, product)
        except IndexError:
            return {
                "alert_id": alert_id,
                "value": None,
                "triggered": False,
                "status": "no_data",
                "message": "No data returned from CO-OPS API.",
            }
        except (KeyError, ValueError, TypeError) as exc:
            return {
                "alert_id": alert_id,
                "value": None,
                "triggered": False,
                "status": "parse_error",
                "message": f"Failed to parse CO-OPS response: {exc}",
            }

        alert["last_value"] = value
        triggered = _compare(value, alert["operator"], alert["threshold"])
        alert["triggered"] = triggered

        if triggered:
            history = alert["trigger_history"]
            history.append({"timestamp": now, "value": value})
            if len(history) > MAX_TRIGGER_HISTORY:
                del history[: len(history) - MAX_TRIGGER_HISTORY]

        return {
            "alert_id": alert_id,
            "value": value,
            "triggered": triggered,
            "status": "ok",
            "message": (
                f"TRIGGERED: {value} {alert['operator']} {alert['threshold']}"
                if triggered
                else f"OK: {value} does not satisfy {alert['operator']} {alert['threshold']}"
            ),
        }

    async def check_all_alerts(self) -> list[dict[str, Any]]:
        """Check all active alerts and return results.

        Iterates over a snapshot (``list(...)``) rather than the live dict:
        each check awaits an HTTP call, and a concurrent
        create/delete/pause tool call can otherwise mutate ``self._alerts``
        mid-iteration, raising "dictionary changed size during iteration".
        An alert deleted after the snapshot was taken (and thus missing by
        the time its turn comes up) is skipped rather than raising.
        """
        results = []
        for alert_id, alert in list(self._alerts.items()):
            if not alert["active"]:
                continue
            try:
                result = await self.check_alert(alert_id)
            except AlertError:
                continue
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
