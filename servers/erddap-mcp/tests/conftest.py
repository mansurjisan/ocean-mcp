"""Shared fixtures for erddap-mcp tests."""

import pytest

from erddap_mcp.client import ERDDAPClient


@pytest.fixture
async def client():
    """Create an ERDDAPClient and close it after the test."""
    c = ERDDAPClient()
    yield c
    await c.close()
