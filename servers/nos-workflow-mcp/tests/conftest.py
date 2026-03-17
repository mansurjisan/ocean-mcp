"""Shared test fixtures."""

import pytest
from unittest.mock import MagicMock

from nos_workflow_mcp.config_reader import ConfigReader


@pytest.fixture
def reader():
    """Create a ConfigReader pointing at the test nos-workflow repo."""
    return ConfigReader(workflow_dir="/tmp/nos-workflow")


@pytest.fixture
def mock_ctx(reader):
    """Create a mock MCP context with the reader in lifespan context."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"config_reader": reader}
    return ctx
