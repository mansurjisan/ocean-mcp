"""Shared fixtures for adcirc-mcp tests."""

import pytest

from adcirc_mcp.client import ADCIRCClient


@pytest.fixture
async def client():
    """Create an ADCIRCClient and close it after the test."""
    c = ADCIRCClient()
    yield c
    await c.close()
