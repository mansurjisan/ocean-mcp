"""Shared fixtures for stofs-mcp tests."""

import pytest

from stofs_mcp.client import STOFSClient


@pytest.fixture
async def client():
    """Create a STOFSClient and close it after the test."""
    c = STOFSClient()
    yield c
    await c.close()
