"""Shared fixtures for schism-mcp tests."""

import pytest

from schism_mcp.client import SchismClient


@pytest.fixture
async def client():
    """Create a SchismClient and close it after the test."""
    c = SchismClient()
    yield c
    await c.close()
