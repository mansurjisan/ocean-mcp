"""Shared test fixtures for alert-mcp."""

import pytest
from unittest.mock import MagicMock

from alert_mcp.alert_manager import AlertManager


@pytest.fixture
def manager():
    """Create a fresh AlertManager."""
    return AlertManager()


@pytest.fixture
def mock_ctx(manager):
    """Create a mock MCP context with the AlertManager in lifespan context."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"alert_manager": manager}
    return ctx
