"""Tests for alert manager and MCP tools."""

import pytest
import httpx
import respx

from alert_mcp.alert_manager import (
    MAX_TRIGGER_HISTORY,
    AlertError,
    AlertManager,
)
from alert_mcp.client import (
    COOPS_API_URL,
    AlertHTTPClient,
    CoopsAPIError,
    RetryTransport,
)
from alert_mcp.tools.alerts import (
    coral_check_alerts,
    coral_create_alert,
    coral_delete_alert,
    coral_get_alert_history,
    coral_list_alerts,
    coral_pause_alert,
    coral_resume_alert,
)


# ---------------------------------------------------------------------------
# AlertManager unit tests
# ---------------------------------------------------------------------------


class TestCreateAlert:
    def test_create_alert(self, manager: AlertManager):
        alert = manager.create_alert(
            station_id="8518750",
            product="water_level",
            operator=">",
            threshold=1.5,
            interval_seconds=300,
        )
        assert alert["station_id"] == "8518750"
        assert alert["product"] == "water_level"
        assert alert["operator"] == ">"
        assert alert["threshold"] == 1.5
        assert alert["interval_seconds"] == 300
        assert alert["active"] is True
        assert alert["triggered"] is False
        assert alert["trigger_history"] == []
        assert alert["id"] in {a["id"] for a in manager.list_alerts()}

    def test_invalid_operator_rejected(self, manager: AlertManager):
        with pytest.raises(AlertError, match="Invalid operator"):
            manager.create_alert(
                station_id="8518750",
                product="water_level",
                operator="==",
                threshold=1.5,
                interval_seconds=300,
            )

    def test_invalid_station_rejected(self, manager: AlertManager):
        with pytest.raises(AlertError, match="Invalid station_id"):
            manager.create_alert(
                station_id="8518750; DROP TABLE",
                product="water_level",
                operator=">",
                threshold=1.5,
                interval_seconds=300,
            )

    def test_invalid_product_rejected(self, manager: AlertManager):
        """A product CO-OPS doesn't support (or alert-mcp can't parse a
        comparable value for) is rejected at creation, not discovered later
        via silent no-data."""
        with pytest.raises(AlertError, match="Invalid product"):
            manager.create_alert(
                station_id="8518750",
                product="not_a_real_product",
                operator=">",
                threshold=1.5,
                interval_seconds=300,
            )

    def test_currents_product_accepted(self, manager: AlertManager):
        """'currents' is a valid product; alphanumeric currents station IDs
        like 'cb0102' are accepted by the station regex."""
        alert = manager.create_alert(
            station_id="cb0102",
            product="currents",
            operator=">",
            threshold=30.0,
            interval_seconds=300,
        )
        assert alert["product"] == "currents"


class TestProductAllowlistRegressionFixes:
    """Regression coverage for the product allowlist itself.

    'one_minute_water_level' and 'ofs_water_level' worked fine before this
    product allowlist existed and are real, live CO-OPS products (verified
    live: both return a normal {"data": [{"v": ...}]} shape via
    date=latest, same as water_level) — they belong back in the allowlist.

    'hourly_height' and 'high_low' are archived/verified-data-only products:
    verified live, querying either with date=latest returns CO-OPS's error
    envelope at every station, always — check_alert hardcodes date=latest,
    so an alert on either product could never pass the create-time probe.
    They're correctly left out of the allowlist.

    'daily_mean' is also a real CO-OPS product, but live verification shows
    it has the SAME date=latest problem as hourly_height/high_low: it only
    returns data for date ranges roughly a month or more in the past, and
    returns CO-OPS's error envelope for date=latest/today/recent or any
    date range within the last ~3-4 weeks, at every Great Lakes station
    tried. Restoring it (as a literal reading of "previously worked" might
    suggest) would just reintroduce the same advertise-but-unreachable
    problem being fixed for hourly_height/high_low, so it is deliberately
    NOT restored.
    """

    def test_one_minute_water_level_accepted(self, manager: AlertManager):
        alert = manager.create_alert(
            station_id="8518750",
            product="one_minute_water_level",
            operator=">",
            threshold=1.0,
            interval_seconds=300,
        )
        assert alert["product"] == "one_minute_water_level"

    def test_ofs_water_level_accepted(self, manager: AlertManager):
        alert = manager.create_alert(
            station_id="8518750",
            product="ofs_water_level",
            operator=">",
            threshold=1.0,
            interval_seconds=300,
        )
        assert alert["product"] == "ofs_water_level"

    def test_hourly_height_rejected(self, manager: AlertManager):
        """Structurally unreachable given check_alert's hardcoded
        date=latest (verified live); not offered as a product."""
        with pytest.raises(AlertError, match="Invalid product"):
            manager.create_alert(
                station_id="8518750",
                product="hourly_height",
                operator=">",
                threshold=1.0,
                interval_seconds=300,
            )

    def test_high_low_rejected(self, manager: AlertManager):
        """Structurally unreachable given check_alert's hardcoded
        date=latest (verified live); not offered as a product."""
        with pytest.raises(AlertError, match="Invalid product"):
            manager.create_alert(
                station_id="8518750",
                product="high_low",
                operator=">",
                threshold=1.0,
                interval_seconds=300,
            )

    def test_daily_mean_rejected(self, manager: AlertManager):
        """Not restored despite being a real CO-OPS product: live
        verification shows it has the same date=latest unreachability
        problem as hourly_height/high_low (see class docstring)."""
        with pytest.raises(AlertError, match="Invalid product"):
            manager.create_alert(
                station_id="9063020",
                product="daily_mean",
                operator=">",
                threshold=1.0,
                interval_seconds=300,
            )


class TestListAlerts:
    def test_list_alerts_empty(self, manager: AlertManager):
        assert manager.list_alerts() == []

    def test_list_alerts_with_alerts(self, manager: AlertManager):
        manager.create_alert("8518750", "water_level", ">", 1.5, 300)
        manager.create_alert("8461490", "water_level", "<", 0.0, 600)
        alerts = manager.list_alerts()
        assert len(alerts) == 2
        station_ids = {a["station_id"] for a in alerts}
        assert station_ids == {"8518750", "8461490"}


class TestDeleteAlert:
    def test_delete_alert(self, manager: AlertManager):
        alert = manager.create_alert("8518750", "water_level", ">", 1.5, 300)
        manager.delete_alert(alert["id"])
        assert manager.list_alerts() == []

    def test_delete_nonexistent(self, manager: AlertManager):
        with pytest.raises(AlertError, match="not found"):
            manager.delete_alert("nonexistent")


class TestPauseResume:
    def test_pause_and_resume(self, manager: AlertManager):
        alert = manager.create_alert("8518750", "water_level", ">", 1.5, 300)
        aid = alert["id"]

        paused = manager.pause_alert(aid)
        assert paused["active"] is False

        resumed = manager.resume_alert(aid)
        assert resumed["active"] is True


# ---------------------------------------------------------------------------
# CO-OPS response fixtures
#
# Shapes below are copied from live requests against
# https://api.tidesandcurrents.noaa.gov/api/prod/datagetter (verified
# 2026-07-28), not guessed:
#   water_level   -> {"data": [{"v": ..., "s": ..., "f": ..., "q": ...}]}
#   predictions   -> {"predictions": [{"t": ..., "v": ...}]}  (no "data" key)
#   currents      -> {"data": [{"t": ..., "s": ..., "d": ..., "b": ...}]}
#                    (speed is "s"; there is no "v" key on currents records)
#   one_minute_water_level / ofs_water_level ->
#       {"metadata": {...}, "data": [{"t": ..., "v": ...}]}
#   error, product genuinely not offered at this station right now
#     (e.g. product=air_gap/salinity/conductivity at a station lacking that
#     sensor) -> HTTP 200, {"error": {"message": "No data was found. This
#     product may not be offered at this station..."}}
#   error, malformed/invalid request (bad station id, unsupported datum, or
#     a product/station combo CO-OPS rejects outright rather than reports
#     "not available") -> HTTP 400, SAME {"error": {"message": "..."}} body
#     shape, e.g. "Wrong Station ID: Please submit a valid station ID" or
#     "There is no MLLW for the station: 9999999".
# ---------------------------------------------------------------------------


def _make_coops_response(value: str) -> dict:
    """Build a minimal CO-OPS water_level JSON response."""
    return {
        "data": [
            {
                "t": "2025-01-15 12:00",
                "v": value,
                "s": "0.01",
                "f": "0,0,0,0",
                "q": "v",
            }
        ]
    }


def _make_predictions_response(value: str) -> dict:
    """Build a minimal CO-OPS tide-predictions response (top-level 'predictions')."""
    return {"predictions": [{"t": "2025-01-15 12:00", "v": value}]}


def _make_currents_response(speed: str) -> dict:
    """Build a minimal CO-OPS currents response ('s' speed key, no 'v')."""
    return {
        "metadata": {"id": "cb0102", "name": "Test Station", "lat": "0", "lon": "0"},
        "data": [{"t": "2025-01-15 12:00", "s": speed, "d": "296", "b": "4"}],
    }


def _make_error_response(message: str) -> dict:
    """Build a CO-OPS error envelope.

    CO-OPS returns this same body shape on both HTTP 200 (product not
    currently offered at this station) and HTTP 400 (malformed/invalid
    request) — the caller picks the status code to wrap it in."""
    return {"error": {"message": message}}


class TestCheckAlert:
    @pytest.mark.asyncio
    @respx.mock
    async def test_check_alert_mocked(self, manager: AlertManager):
        """Check an alert against a mocked CO-OPS response (no trigger)."""
        alert = manager.create_alert("8518750", "water_level", ">", 2.0, 300)
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(200, json=_make_coops_response("1.05"))
        )

        result = await manager.check_alert(alert["id"])

        assert result["alert_id"] == alert["id"]
        assert result["value"] == 1.05
        assert result["triggered"] is False
        assert result["status"] == "ok"
        assert "OK" in result["message"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_check_alert_triggered(self, manager: AlertManager):
        """Check that a value exceeding the threshold triggers the alert."""
        alert = manager.create_alert("8518750", "water_level", ">", 1.0, 300)
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(200, json=_make_coops_response("1.75"))
        )

        result = await manager.check_alert(alert["id"])

        assert result["triggered"] is True
        assert result["value"] == 1.75
        assert result["status"] == "ok"
        assert "TRIGGERED" in result["message"]
        assert alert["triggered"] is True
        assert len(alert["trigger_history"]) == 1
        assert alert["trigger_history"][0]["value"] == 1.75

    @pytest.mark.asyncio
    @respx.mock
    async def test_check_alert_not_triggered(self, manager: AlertManager):
        """Check that a value below threshold does not trigger."""
        alert = manager.create_alert("8518750", "water_level", ">=", 2.0, 300)
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(200, json=_make_coops_response("1.99"))
        )

        result = await manager.check_alert(alert["id"])

        assert result["triggered"] is False
        assert result["value"] == 1.99
        assert alert["trigger_history"] == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_check_alert_no_data(self, manager: AlertManager):
        """An empty 'data' list is reported as no_data, not a parse error."""
        alert = manager.create_alert("8518750", "water_level", ">", 1.0, 300)
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(200, json={"data": []})
        )

        result = await manager.check_alert(alert["id"])

        assert result["status"] == "no_data"
        assert result["value"] is None
        assert "No data" in result["message"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_check_alert_http_error(self, manager: AlertManager):
        """A transport-level failure is reported as http_error, not raised."""
        alert = manager.create_alert("8518750", "water_level", ">", 1.0, 300)
        respx.get(COOPS_API_URL).mock(side_effect=httpx.ConnectError("refused"))

        result = await manager.check_alert(alert["id"])

        assert result["status"] == "http_error"
        assert result["value"] is None

    async def test_check_alert_nonexistent(self, manager: AlertManager):
        with pytest.raises(AlertError, match="not found"):
            await manager.check_alert("nonexistent")


class TestPredictionsProduct:
    """Regression test: predictions responses nest records under
    'predictions', not 'data' — alerts on product='predictions' used to get
    an empty list forever and never fire."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_predictions_uses_predictions_key(self, manager: AlertManager):
        alert = manager.create_alert("8518750", "predictions", ">", 1.0, 300)
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(200, json=_make_predictions_response("1.5"))
        )

        result = await manager.check_alert(alert["id"])

        assert result["status"] == "ok"
        assert result["value"] == 1.5
        assert result["triggered"] is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_predictions_data_key_absent_is_not_used(self, manager: AlertManager):
        """A predictions response has no 'data' key at all; confirm we don't
        fall back to it and silently report no_data."""
        alert = manager.create_alert("8518750", "predictions", ">", 1.0, 300)
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(
                200, json={"predictions": [{"t": "x", "v": "2.0"}]}
            )
        )

        result = await manager.check_alert(alert["id"])

        assert result["status"] == "ok"
        assert result["value"] == 2.0


class TestCurrentsProduct:
    """Regression test: currents records key the scalar as 's' (speed), not
    'v' — the old code read records[-1]["v"] which doesn't exist for
    currents and would raise a parse error on every check."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_currents_uses_speed_key(self, manager: AlertManager):
        alert = manager.create_alert("cb0102", "currents", ">", 30.0, 300)
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(200, json=_make_currents_response("46.4"))
        )

        result = await manager.check_alert(alert["id"])

        assert result["status"] == "ok"
        assert result["value"] == 46.4
        assert result["triggered"] is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_currents_predictions_uses_velocity_major(
        self, manager: AlertManager
    ):
        """currents_predictions nests records under current_predictions.cp,
        keyed by 'Velocity_Major' — yet another shape than 'currents'."""
        alert = manager.create_alert("cb0102", "currents_predictions", ">", 50.0, 300)
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "current_predictions": {
                        "units": "meters, cm/s",
                        "cp": [
                            {
                                "Time": "2026-07-27 22:56",
                                "Velocity_Major": 58.8,
                                "meanFloodDir": 281,
                                "meanEbbDir": 101,
                                "Bin": "14",
                                "Depth": "16.8",
                            }
                        ],
                    }
                },
            )
        )

        result = await manager.check_alert(alert["id"])

        assert result["status"] == "ok"
        assert result["value"] == 58.8
        assert result["triggered"] is True


class TestOneMinuteAndOfsWaterLevelProducts:
    """Regression test: 'one_minute_water_level' and 'ofs_water_level' were
    dropped from the product allowlist by mistake even though both worked
    fine before the allowlist existed. Verified live: both return the same
    {"data": [{"v": ...}]} shape as 'water_level'."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_one_minute_water_level_uses_data_v(self, manager: AlertManager):
        alert = manager.create_alert("8518750", "one_minute_water_level", ">", 1.0, 300)
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(200, json=_make_coops_response("1.318"))
        )

        result = await manager.check_alert(alert["id"])

        assert result["status"] == "ok"
        assert result["value"] == 1.318
        assert result["triggered"] is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_ofs_water_level_uses_data_v(self, manager: AlertManager):
        alert = manager.create_alert("8518750", "ofs_water_level", ">", 1.0, 300)
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(200, json=_make_coops_response("1.264"))
        )

        result = await manager.check_alert(alert["id"])

        assert result["status"] == "ok"
        assert result["value"] == 1.264
        assert result["triggered"] is True


class TestCoopsErrorEnvelope:
    """Regression test: CO-OPS returns an {"error": {...}} body for a bad
    station_id or an unsupported product/station combo, on either HTTP 200
    or HTTP 400 depending on which — a plain raise_for_status()-then-check
    approach only ever sees the 200 case. It must be surfaced (with the
    real NOAA message), not swallowed into a generic message forever."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_error_envelope_surfaced_on_http_200(self, manager: AlertManager):
        """A structurally valid request for a product this station doesn't
        currently offer is CO-OPS's HTTP 200 error-envelope case (verified
        live, e.g. product=salinity/conductivity/air_gap at a station
        lacking that sensor)."""
        alert = manager.create_alert("8518750", "salinity", ">", 1.0, 300)
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(
                200,
                json=_make_error_response(
                    "No data was found. This product may not be offered "
                    "at this station at the requested time."
                ),
            )
        )

        result = await manager.check_alert(alert["id"])

        assert result["status"] == "coops_error"
        assert result["value"] is None
        assert result["triggered"] is False
        assert "No data was found" in result["message"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_error_envelope_surfaced_on_http_400(self, manager: AlertManager):
        """A bad station_id is CO-OPS's HTTP 400 error-envelope case
        (verified live against a nonexistent station: 9999999 with
        product=water_level/datum=MLLW returns HTTP 400 with this exact
        message). This is the case a plain raise_for_status()-first
        implementation would misreport as a generic 'http_error' and lose
        the real NOAA message entirely."""
        alert = manager.create_alert("9999999", "water_level", ">", 1.0, 300)
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(
                400,
                json=_make_error_response("There is no MLLW for the station: 9999999"),
            )
        )

        result = await manager.check_alert(alert["id"])

        assert result["status"] == "coops_error"
        assert result["value"] is None
        assert result["triggered"] is False
        assert "no MLLW" in result["message"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_error_envelope_wrong_station_for_product(
        self, manager: AlertManager
    ):
        """Requesting 'currents' at a station id CO-OPS doesn't recognize
        for that product returns this exact message at HTTP 400 (verified
        live), not HTTP 200."""
        alert = manager.create_alert("8518750", "currents", ">", 1.0, 300)
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(
                400,
                json=_make_error_response(
                    "Wrong Station ID: Please submit a valid station ID"
                ),
            )
        )

        result = await manager.check_alert(alert["id"])

        assert result["status"] == "coops_error"
        assert "Wrong Station ID" in result["message"]


class TestAlertHistory:
    @pytest.mark.asyncio
    @respx.mock
    async def test_alert_history(self, manager: AlertManager):
        """Verify trigger history accumulates across multiple checks."""
        alert = manager.create_alert("8518750", "water_level", ">", 1.0, 300)

        for val in ["1.50", "0.80", "2.10"]:
            respx.get(COOPS_API_URL).mock(
                return_value=httpx.Response(200, json=_make_coops_response(val))
            )
            await manager.check_alert(alert["id"])

        history = manager.get_alert_history(alert["id"])
        # 1.50 > 1.0 -> triggered, 0.80 not, 2.10 > 1.0 -> triggered
        assert len(history) == 2
        assert history[0]["value"] == 1.50
        assert history[1]["value"] == 2.10


class TestTriggerHistoryCap:
    """trigger_history must never grow unbounded across a long-running
    process; it's capped at MAX_TRIGGER_HISTORY, keeping the most recent
    entries."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_trigger_history_capped(self, manager: AlertManager):
        alert = manager.create_alert("8518750", "water_level", ">", 0.0, 300)
        # Pre-fill history right up to the cap.
        alert["trigger_history"] = [
            {"timestamp": f"t{i}", "value": float(i)}
            for i in range(MAX_TRIGGER_HISTORY)
        ]
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(200, json=_make_coops_response("99.9"))
        )

        await manager.check_alert(alert["id"])

        history = manager.get_alert_history(alert["id"])
        assert len(history) == MAX_TRIGGER_HISTORY
        # Oldest entry (t0) was dropped; newest (99.9) was appended.
        assert history[0]["timestamp"] == "t1"
        assert history[-1]["value"] == 99.9


class TestConcurrentMutationSafety:
    """check_all_alerts iterates a snapshot of the alerts dict, since each
    check awaits an HTTP call and FastMCP tool calls can interleave on the
    event loop — a live dict iterator would raise 'dictionary changed size
    during iteration' if another tool call deletes an alert mid-cycle."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_check_all_alerts_safe_when_alert_deleted_mid_iteration(
        self, manager: AlertManager
    ):
        a1 = manager.create_alert("8518750", "water_level", ">", 100.0, 300)
        a2 = manager.create_alert("8461490", "water_level", ">", 100.0, 300)

        def _side_effect(request):
            # Simulate a concurrent coral_delete_alert call landing while
            # check_all_alerts is mid-iteration (during a1's HTTP call).
            manager.delete_alert(a2["id"])
            return httpx.Response(200, json=_make_coops_response("1.0"))

        respx.get(COOPS_API_URL).mock(side_effect=_side_effect)

        results = await manager.check_all_alerts()

        # No RuntimeError from mutating self._alerts mid-iteration, and the
        # alert deleted mid-flight is skipped rather than raising.
        assert [r["alert_id"] for r in results] == [a1["id"]]
        assert [a["id"] for a in manager.list_alerts()] == [a1["id"]]


class TestRetryTransportWiring:
    @pytest.mark.asyncio
    async def test_client_uses_retry_transport(self):
        """The shared httpx client is mounted on the RetryTransport, and is
        reused across calls rather than opened/closed per check."""
        c = AlertHTTPClient()
        client = await c._get_client()
        try:
            assert isinstance(client._transport, RetryTransport)
            assert await c._get_client() is client
        finally:
            await c.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_retries_transient_503_then_succeeds(self):
        """A 503 followed by a 200 is retried through to success."""
        respx.get(COOPS_API_URL).mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(200, json=_make_coops_response("1.0")),
            ]
        )
        c = AlertHTTPClient(backoff_factor=0)
        try:
            data = await c.fetch({"station": "8518750", "product": "water_level"})
        finally:
            await c.close()

        assert data["data"][0]["v"] == "1.0"


class TestClientErrorEnvelopeStatusCodes:
    """Direct unit tests on AlertHTTPClient.fetch() for the core fix: the
    body must be checked for CO-OPS's {"error": {...}} envelope
    independent of status code, since CO-OPS puts it on both HTTP 200 and
    HTTP 400 (verified live against
    https://api.tidesandcurrents.noaa.gov/api/prod/datagetter)."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_raises_coops_api_error_on_http_200_envelope(self):
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(
                200,
                json=_make_error_response(
                    "No data was found. This product may not be offered "
                    "at this station at the requested time."
                ),
            )
        )
        c = AlertHTTPClient(backoff_factor=0)
        try:
            with pytest.raises(CoopsAPIError, match="No data was found"):
                await c.fetch({"station": "8518750", "product": "air_gap"})
        finally:
            await c.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_raises_coops_api_error_on_http_400_envelope(self):
        """The regression this fix addresses: a plain
        raise_for_status()-then-check-body implementation would raise a
        generic httpx.HTTPStatusError here instead, discarding this real
        NOAA message. Verified live: a bad station id returns exactly this
        body at HTTP 400, not 200."""
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(
                400,
                json=_make_error_response(
                    "Wrong Station ID: Please submit a valid station ID"
                ),
            )
        )
        c = AlertHTTPClient(backoff_factor=0)
        try:
            with pytest.raises(CoopsAPIError, match="Wrong Station ID"):
                await c.fetch({"station": "bad", "product": "water_level"})
        finally:
            await c.close()

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_raises_http_status_error_on_non_envelope_failure(self):
        """A non-2xx response whose body isn't the CO-OPS error-envelope
        shape (e.g. an upstream gateway error page) still surfaces as the
        standard httpx.HTTPStatusError rather than being misreported as a
        CoopsAPIError."""
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(502, text="<html>Bad Gateway</html>")
        )
        c = AlertHTTPClient(backoff_factor=0, max_retries=0)
        try:
            with pytest.raises(httpx.HTTPStatusError):
                await c.fetch({"station": "8518750", "product": "water_level"})
        finally:
            await c.close()


# ---------------------------------------------------------------------------
# MCP tool integration tests (via mock context)
# ---------------------------------------------------------------------------


class TestToolCreateAlert:
    @pytest.mark.asyncio
    @respx.mock
    async def test_tool_create_alert(self, mock_ctx):
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(200, json=_make_coops_response("1.05"))
        )

        result = await coral_create_alert(
            mock_ctx,
            station_id="8518750",
            operator=">",
            threshold=1.5,
        )
        assert "Alert Created" in result
        assert "8518750" in result
        assert ">" in result

    @pytest.mark.asyncio
    async def test_tool_create_alert_invalid_operator(self, mock_ctx):
        result = await coral_create_alert(
            mock_ctx,
            station_id="8518750",
            operator="!=",
            threshold=1.5,
        )
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_tool_create_alert_invalid_product(self, mock_ctx):
        result = await coral_create_alert(
            mock_ctx,
            station_id="8518750",
            operator=">",
            threshold=1.5,
            product="not_a_real_product",
        )
        assert "Error" in result

    @pytest.mark.asyncio
    @respx.mock
    async def test_tool_create_alert_rejects_coops_error(self, mock_ctx, manager):
        """A station/product combination CO-OPS itself rejects outright
        (HTTP 400, verified live) is caught by the immediate live probe and
        never left dangling as a live alert."""
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(
                400,
                json=_make_error_response(
                    "Wrong Station ID: Please submit a valid station ID"
                ),
            )
        )

        result = await coral_create_alert(
            mock_ctx,
            station_id="8518750",
            operator=">",
            threshold=1.5,
            product="currents",
        )

        assert "Error" in result
        assert "Wrong Station ID" in result
        assert manager.list_alerts() == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_tool_create_alert_rejects_http_error(self, mock_ctx, manager):
        """A persistent transport failure during the create-time probe also
        blocks creation, not just a coops_error status — the probe gate
        rejects on any non-'ok' result."""
        respx.get(COOPS_API_URL).mock(side_effect=httpx.ConnectError("refused"))

        result = await coral_create_alert(
            mock_ctx,
            station_id="8518750",
            operator=">",
            threshold=1.5,
        )

        assert "Error" in result
        assert manager.list_alerts() == []


class TestToolListAlerts:
    @pytest.mark.asyncio
    async def test_tool_list_empty(self, mock_ctx):
        result = await coral_list_alerts(mock_ctx)
        assert "No alerts" in result

    @pytest.mark.asyncio
    async def test_tool_list_with_alerts(self, mock_ctx, manager):
        manager.create_alert("8518750", "water_level", ">", 1.5, 300)
        result = await coral_list_alerts(mock_ctx)
        assert "8518750" in result
        assert "Active" in result


class TestToolCheckAlerts:
    @pytest.mark.asyncio
    async def test_tool_check_no_active(self, mock_ctx):
        result = await coral_check_alerts(mock_ctx)
        assert "No active alerts" in result

    @pytest.mark.asyncio
    @respx.mock
    async def test_tool_check_surfaces_coops_error(self, mock_ctx, manager):
        """A misconfigured alert's CO-OPS error is visible in the check
        results, not hidden behind a generic message."""
        manager.create_alert("9999999", "water_level", ">", 1.0, 300)
        respx.get(COOPS_API_URL).mock(
            return_value=httpx.Response(
                200,
                json=_make_error_response("There is no MLLW for the station: 9999999"),
            )
        )

        result = await coral_check_alerts(mock_ctx)

        assert "COOPS_ERROR" in result
        assert "no MLLW" in result


class TestToolPauseAlert:
    @pytest.mark.asyncio
    async def test_tool_pause(self, mock_ctx, manager):
        alert = manager.create_alert("8518750", "water_level", ">", 1.5, 300)
        result = await coral_pause_alert(mock_ctx, alert_id=alert["id"])
        assert "paused" in result

    @pytest.mark.asyncio
    async def test_tool_pause_nonexistent(self, mock_ctx):
        result = await coral_pause_alert(mock_ctx, alert_id="nope")
        assert "Error" in result


class TestToolResumeAlert:
    @pytest.mark.asyncio
    async def test_tool_resume(self, mock_ctx, manager):
        alert = manager.create_alert("8518750", "water_level", ">", 1.5, 300)
        manager.pause_alert(alert["id"])

        result = await coral_resume_alert(mock_ctx, alert_id=alert["id"])

        assert "active" in result
        assert manager.list_alerts()[0]["active"] is True

    @pytest.mark.asyncio
    async def test_tool_resume_nonexistent(self, mock_ctx):
        result = await coral_resume_alert(mock_ctx, alert_id="nope")
        assert "Error" in result


class TestToolDeleteAlert:
    @pytest.mark.asyncio
    async def test_tool_delete(self, mock_ctx, manager):
        alert = manager.create_alert("8518750", "water_level", ">", 1.5, 300)
        result = await coral_delete_alert(mock_ctx, alert_id=alert["id"])
        assert "deleted" in result
        assert manager.list_alerts() == []


class TestToolAlertHistory:
    @pytest.mark.asyncio
    async def test_tool_history_empty(self, mock_ctx, manager):
        alert = manager.create_alert("8518750", "water_level", ">", 1.5, 300)
        result = await coral_get_alert_history(mock_ctx, alert_id=alert["id"])
        assert "No trigger history" in result

    @pytest.mark.asyncio
    async def test_tool_history_nonexistent(self, mock_ctx):
        result = await coral_get_alert_history(mock_ctx, alert_id="nope")
        assert "Error" in result
