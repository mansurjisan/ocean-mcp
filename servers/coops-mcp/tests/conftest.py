"""Shared fixtures for coops-mcp tests."""

import pytest

from coops_mcp.client import COOPSClient


@pytest.fixture
async def client():
    """Create a COOPSClient and close it after the test."""
    c = COOPSClient()
    yield c
    await c.close()
