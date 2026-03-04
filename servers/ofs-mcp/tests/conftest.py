"""Shared fixtures for ofs-mcp tests."""

import pytest

from ofs_mcp.client import OFSClient


@pytest.fixture
async def client():
    """Create an OFSClient and close it after the test."""
    c = OFSClient()
    yield c
    await c.close()
