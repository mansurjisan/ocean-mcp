"""Shared test fixtures for hpc-system-mcp."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from hpc_system_mcp.executor import CommandExecutor


@pytest.fixture
def executor():
    """Create a CommandExecutor."""
    return CommandExecutor()


@pytest.fixture
def mock_executor():
    """Create a mock executor for tool tests."""
    ex = MagicMock(spec=CommandExecutor)
    ex.run = AsyncMock()
    ex.run_module = AsyncMock()
    return ex


@pytest.fixture
def mock_ctx(mock_executor):
    """Create a mock MCP context with the executor in lifespan context."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"executor": mock_executor}
    return ctx
