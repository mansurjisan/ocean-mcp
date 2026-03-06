"""Integration tests for adcirc-mcp that hit real ADCIRC wiki.

These tests make actual HTTP requests and should be run with:
    pytest tests/test_live.py -m integration -v

They are excluded from CI unit test runs.
"""

import pytest

from adcirc_mcp.client import ADCIRCClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_wiki_search():
    """Search the real ADCIRC wiki for 'fort.15'."""
    client = ADCIRCClient()
    try:
        results = await client.search_wiki("fort.15", limit=5)
        assert len(results) > 0, "Expected at least 1 result from ADCIRC wiki"
        assert any("fort" in r["title"].lower() for r in results)
    finally:
        await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_wiki_fetch_page():
    """Fetch a real page from the ADCIRC wiki."""
    client = ADCIRCClient()
    try:
        content = await client.fetch_wiki_page("Main_Page")
        assert len(content) > 0, "Expected non-empty content from ADCIRC wiki main page"
    finally:
        await client.close()
