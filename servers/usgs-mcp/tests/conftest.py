"""Shared fixtures for usgs-mcp tests."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from usgs_mcp.client import USGSClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    """Load a fixture file as text."""
    return (FIXTURES_DIR / name).read_text()


def load_json_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    return json.loads(load_fixture(name))


@pytest.fixture
async def client():
    """Create a USGSClient for integration tests."""
    c = USGSClient()
    yield c
    await c.close()


@pytest.fixture
def usgs_client():
    """Create a USGSClient instance for unit tests (not connected)."""
    return USGSClient()


@pytest.fixture
def ctx(usgs_client):
    """Create a mock MCP Context with a USGSClient in lifespan context."""
    mock_ctx = MagicMock()
    mock_ctx.request_context.lifespan_context = {"usgs_client": usgs_client}
    return mock_ctx
