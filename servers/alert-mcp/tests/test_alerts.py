"""Tests for alert manager and MCP tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from alert_mcp.alert_manager import AlertError, AlertManager
from alert_mcp.tools.alerts import (
    coral_check_alerts,
    coral_create_alert,
    coral_delete_alert,
    coral_get_alert_history,
    coral_list_alerts,
    coral_pause_alert,
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


def _make_coops_response(value: str) -> dict:
    """Build a minimal CO-OPS JSON response."""
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


class TestCheckAlert:
    @pytest.mark.asyncio
    async def test_check_alert_mocked(self, manager: AlertManager):
        """Check an alert against a mocked CO-OPS response (no trigger)."""
        alert = manager.create_alert("8518750", "water_level", ">", 2.0, 300)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _make_coops_response("1.05")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "alert_mcp.alert_manager.httpx.AsyncClient", return_value=mock_client
        ):
            result = await manager.check_alert(alert["id"])

        assert result["alert_id"] == alert["id"]
        assert result["value"] == 1.05
        assert result["triggered"] is False
        assert "OK" in result["message"]

    @pytest.mark.asyncio
    async def test_check_alert_triggered(self, manager: AlertManager):
        """Check that a value exceeding the threshold triggers the alert."""
        alert = manager.create_alert("8518750", "water_level", ">", 1.0, 300)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _make_coops_response("1.75")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "alert_mcp.alert_manager.httpx.AsyncClient", return_value=mock_client
        ):
            result = await manager.check_alert(alert["id"])

        assert result["triggered"] is True
        assert result["value"] == 1.75
        assert "TRIGGERED" in result["message"]
        assert alert["triggered"] is True
        assert len(alert["trigger_history"]) == 1
        assert alert["trigger_history"][0]["value"] == 1.75

    @pytest.mark.asyncio
    async def test_check_alert_not_triggered(self, manager: AlertManager):
        """Check that a value below threshold does not trigger."""
        alert = manager.create_alert("8518750", "water_level", ">=", 2.0, 300)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _make_coops_response("1.99")

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "alert_mcp.alert_manager.httpx.AsyncClient", return_value=mock_client
        ):
            result = await manager.check_alert(alert["id"])

        assert result["triggered"] is False
        assert result["value"] == 1.99
        assert alert["trigger_history"] == []


class TestAlertHistory:
    @pytest.mark.asyncio
    async def test_alert_history(self, manager: AlertManager):
        """Verify trigger history accumulates across multiple checks."""
        alert = manager.create_alert("8518750", "water_level", ">", 1.0, 300)

        for val in ["1.50", "0.80", "2.10"]:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.raise_for_status = MagicMock()
            mock_response.json.return_value = _make_coops_response(val)

            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)

            with patch(
                "alert_mcp.alert_manager.httpx.AsyncClient",
                return_value=mock_client,
            ):
                await manager.check_alert(alert["id"])

        history = manager.get_alert_history(alert["id"])
        # 1.50 > 1.0 -> triggered, 0.80 not, 2.10 > 1.0 -> triggered
        assert len(history) == 2
        assert history[0]["value"] == 1.50
        assert history[1]["value"] == 2.10


# ---------------------------------------------------------------------------
# MCP tool integration tests (via mock context)
# ---------------------------------------------------------------------------


class TestToolCreateAlert:
    @pytest.mark.asyncio
    async def test_tool_create_alert(self, mock_ctx):
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
