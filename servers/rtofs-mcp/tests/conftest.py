"""Shared fixtures for RTOFS MCP tests."""

from pathlib import Path

import pytest

from rtofs_mcp.client import RTOFSClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
async def client():
    """Create and clean up an RTOFSClient."""
    c = RTOFSClient()
    yield c
    await c.close()


def load_fixture(name: str) -> str:
    """Load a fixture file as text."""
    return (FIXTURES_DIR / name).read_text()
