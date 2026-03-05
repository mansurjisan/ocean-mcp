"""Shared fixtures for winds-mcp tests."""

import pytest

from winds_mcp.client import WindsClient


@pytest.fixture
async def client():
    """Create a WindsClient and close it after the test."""
    c = WindsClient()
    yield c
    await c.close()
