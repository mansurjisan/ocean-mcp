"""Shared test fixtures for alert-mcp."""

import pytest
from unittest.mock import MagicMock

from alert_mcp.alert_manager import AlertManager
from alert_mcp.client import AlertHTTPClient


@pytest.fixture
def manager():
    """Create a fresh AlertManager with backoff_factor=0 so RetryTransport
    replays any transient-failure mocks instantly instead of sleeping."""
    return AlertManager(client=AlertHTTPClient(backoff_factor=0))


@pytest.fixture
def mock_ctx(manager):
    """Create a mock MCP context with the AlertManager in lifespan context."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"alert_manager": manager}
    return ctx
