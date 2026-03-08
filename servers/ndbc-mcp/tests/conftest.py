"""Shared fixtures for ndbc-mcp tests."""

import pytest

from ndbc_mcp.client import NDBCClient


@pytest.fixture
async def client():
    """Create an NDBCClient and close it after the test."""
    c = NDBCClient()
    yield c
    await c.close()
