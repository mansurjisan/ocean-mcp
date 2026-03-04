"""Shared fixtures for recon-mcp tests."""

import pytest

from recon_mcp.client import ReconClient


@pytest.fixture
async def client():
    """Create a ReconClient and close it after the test."""
    c = ReconClient()
    yield c
    await c.close()
