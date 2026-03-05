"""Shared fixtures for ww3-mcp tests."""

import pytest

from ww3_mcp.client import WW3Client


@pytest.fixture
async def client():
    """Create a WW3Client and close it after the test."""
    c = WW3Client()
    yield c
    await c.close()
