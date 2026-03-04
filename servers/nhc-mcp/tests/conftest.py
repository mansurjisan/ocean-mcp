"""Shared fixtures for nhc-mcp tests."""

import pytest

from nhc_mcp.client import NHCClient


@pytest.fixture
async def client():
    """Create an NHCClient and close it after the test."""
    c = NHCClient()
    yield c
    await c.close()
