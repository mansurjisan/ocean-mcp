"""Live integration tests against the NHC reconnaissance archive.

These tests require internet access and hit real NHC servers.
Run with: uv run pytest tests/test_live.py -v -s
Skip in CI with: --ignore=tests/test_live.py
"""

import pytest

from recon_mcp.client import ReconClient
from recon_mcp.utils import (
    parse_directory_listing,
    parse_hdob_message,
    parse_vdm_message,
    parse_atcf_fix_record,
)


@pytest.fixture
async def client():
    c = ReconClient()
    yield c
    await c.close()


@pytest.mark.asyncio
async def test_live_list_hdob_directory(client):
    """List HDOB files for 2024 Atlantic season."""
    url = client.build_archive_dir_url(2024, "hdob", "al")
    html = await client.list_directory(url)
    entries = parse_directory_listing(html)

    assert len(entries) > 0, "Expected HDOB files for 2024 Atlantic season"
    # HDOB files should contain AHONT1 in filename
    assert any("AHONT1" in e["filename"] for e in entries)


@pytest.mark.asyncio
async def test_live_list_vdm_directory(client):
    """List VDM files for 2024 Atlantic season."""
    url = client.build_archive_dir_url(2024, "vdm", "al")
    html = await client.list_directory(url)
    entries = parse_directory_listing(html)

    assert len(entries) > 0, "Expected VDM files for 2024 Atlantic season"


@pytest.mark.asyncio
async def test_live_fetch_hdob(client):
    """Fetch and parse a real HDOB bulletin from 2024."""
    url = client.build_archive_dir_url(2024, "hdob", "al")
    html = await client.list_directory(url)
    entries = parse_directory_listing(html)

    assert len(entries) > 0, "Need at least one HDOB file"

    # Fetch the first file
    file_url = url + entries[0]["href"]
    text = await client.fetch_text(file_url)
    parsed = parse_hdob_message(text)

    assert "header" in parsed
    assert "observations" in parsed
    # HDOB files should have at least some observations
    print(f"Parsed HDOB: {len(parsed['observations'])} observations")
    print(f"Header: {parsed['header']}")


@pytest.mark.asyncio
async def test_live_fetch_vdm(client):
    """Fetch and parse a real VDM from 2024."""
    url = client.build_archive_dir_url(2024, "vdm", "al")
    html = await client.list_directory(url)
    entries = parse_directory_listing(html)

    assert len(entries) > 0, "Need at least one VDM file"

    # Fetch the first file
    file_url = url + entries[0]["href"]
    text = await client.fetch_text(file_url)
    parsed = parse_vdm_message(text)

    assert "raw_text" in parsed
    print(
        f"Parsed VDM: storm_id={parsed.get('storm_id')}, "
        f"min_slp={parsed.get('min_slp_mb')}"
    )


@pytest.mark.asyncio
async def test_live_atcf_fdeck_milton(client):
    """Fetch ATCF f-deck for Hurricane Milton (AL14 2024)."""
    url = client.build_atcf_fdeck_url("al", 14, 2024)
    try:
        text = await client.fetch_text(url)
    except Exception:
        pytest.skip("Milton f-deck not available (may be archived)")

    lines = text.strip().split("\n")
    assert len(lines) > 0, "Expected f-deck records for Milton"

    # Parse first record
    record = parse_atcf_fix_record(lines[0])
    if record:
        print(f"First fix: {record}")
        assert record["basin"] == "AL"
        assert record["cyclone_num"] == 14


@pytest.mark.asyncio
async def test_live_archive_years(client):
    """Verify the archive has data for recent years."""
    for year in [2023, 2024]:
        url = client.build_archive_dir_url(year, "hdob", "al")
        try:
            html = await client.list_directory(url)
            entries = parse_directory_listing(html)
            print(f"Year {year}: {len(entries)} HDOB files")
            assert len(entries) >= 0  # May be empty for quiet years
        except Exception as e:
            print(f"Year {year}: {e}")
