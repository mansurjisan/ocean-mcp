"""Integration tests for schism-mcp that hit real SCHISM documentation.

These tests make actual HTTP requests and should be run with:
    pytest tests/test_live.py -m integration -v

They are excluded from CI unit test runs.
"""

import pytest

from schism_mcp.client import KNOWN_PAGES, SchismClient


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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_fetch_docs_param_nml_page():
    """Fetch the param.nml page specifically.

    This is the exact page that was 100% dead before this fix: the old path
    (input-output/param.nml.html) 404s on the live site, which restructured
    its docs under /master/ and renamed the page to input-output/param.html.
    Regression coverage for schism_fetch_docs against a mocked HTML blob
    can't catch this class of bug (a site restructure) — only a real
    request to the live endpoint can.
    """
    client = SchismClient()
    try:
        content = await client.fetch_doc_page("input-output/param.html")
        assert len(content) > 0
        assert "dt" in content.lower() or "namelist" in content.lower()
    finally:
        await client.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_live_all_known_pages_resolve():
    """Every path in KNOWN_PAGES must actually resolve on the live site.

    schism_search_docs/schism_fetch_docs are backed entirely by this static
    list (see client.py), so a page rename or removal upstream silently
    breaks a tool with no local signal — mocked unit tests replay whatever
    URL they're given and can't catch a site restructure. This test fetches
    every entry for real and fails loudly (with the offending path) the
    moment one goes stale, the same way the original bug (all 16 old paths
    404ing) should have been caught.
    """
    client = SchismClient()
    failures = []
    try:
        for page in KNOWN_PAGES:
            try:
                content = await client.fetch_doc_page(page["path"])
                if not content:
                    failures.append(f"{page['path']}: empty content")
            except (
                Exception
            ) as exc:  # collect every failure instead of aborting on the first
                failures.append(f"{page['path']}: {exc}")
    finally:
        await client.close()

    assert not failures, "Stale KNOWN_PAGES entries:\n" + "\n".join(failures)
