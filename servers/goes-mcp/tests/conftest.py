"""Shared fixtures for goes-mcp tests."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from goes_mcp.client import GOESClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file by name."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


def load_fixture_bytes(name: str) -> bytes:
    """Load a binary fixture file by name."""
    with open(FIXTURES_DIR / name, "rb") as f:
        return f.read()


@pytest.fixture
def goes_client() -> GOESClient:
    """Create a bare GOESClient (httpx will be intercepted by respx)."""
    return GOESClient()


@pytest.fixture
def ctx(goes_client: GOESClient) -> MagicMock:
    """Create a mock MCP Context wired to the GOESClient fixture."""
    mock_ctx = MagicMock()
    mock_ctx.request_context.lifespan_context = {"goes_client": goes_client}
    return mock_ctx


@pytest.fixture
def slider_times_fixture() -> dict:
    """Load the SLIDER latest_times fixture."""
    return load_fixture("slider_latest_times.json")


@pytest.fixture
def test_image_bytes() -> bytes:
    """Load the test JPEG image bytes."""
    return load_fixture_bytes("test_image.jpg")
