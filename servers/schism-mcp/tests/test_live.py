"""Integration tests for schism-mcp that hit real SCHISM documentation.

These tests make actual HTTP requests and should be run with:
    pytest tests/test_live.py -m integration -v

They are excluded from CI unit test runs.
"""

import pytest

from schism_mcp.client import SchismClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_search_docs():
    """Search the SCHISM documentation for 'param.nml'."""
    client = SchismClient()
    try:
        results = await client.search_docs("param.nml")
        assert len(results) > 0, "Expected at least 1 result for 'param.nml'"
    finally:
        await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_fetch_docs():
    """Fetch a real page from SCHISM docs site."""
    client = SchismClient()
    try:
        content = await client.fetch_doc_page("index.html")
        assert len(content) > 0, "Expected non-empty content from SCHISM docs"
    finally:
        await client.close()
