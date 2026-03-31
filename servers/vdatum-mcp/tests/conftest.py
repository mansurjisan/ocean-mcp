"""Shared test fixtures."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    return ctx
