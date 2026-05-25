"""Mocked HTTP tests for NHCClient using respx."""

import time

import httpx
import pytest
import respx

from nhc_mcp.client import (
    NHCClient,
    CURRENT_STORMS_URL,
    HURDAT2_CACHE_TTL_S,
    HURDAT2_INDEX_URL,
    HURDAT2_URLS,
    NHCAPIError,
)
from nhc_mcp.utils import ARCGIS_BASE_URL


@pytest.fixture
async def client():
    c = NHCClient(backoff_factor=0)
    yield c
    await c.close()


@respx.mock
@pytest.mark.asyncio
async def test_get_active_storms_with_data(client):
    """Test fetching active storms when storms exist."""
    mock_response = {
        "activeStorms": [
            {
                "id": "al052024",
                "binNumber": "AT5",
                "name": "Milton",
                "classification": "HU",
                "intensity": "150",
                "pressure": "897",
            }
        ]
    }
    respx.get(CURRENT_STORMS_URL).mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    storms = await client.get_active_storms()
    assert len(storms) == 1
    assert storms[0]["name"] == "Milton"
    assert storms[0]["binNumber"] == "AT5"


@respx.mock
@pytest.mark.asyncio
async def test_get_active_storms_empty(client):
    """Test fetching active storms when no storms are active."""
    respx.get(CURRENT_STORMS_URL).mock(
        return_value=httpx.Response(200, json={"activeStorms": []})
    )

    storms = await client.get_active_storms()
    assert storms == []


@respx.mock
@pytest.mark.asyncio
async def test_get_best_track_atcf(client):
    """Test fetching ATCF B-deck data."""
    sample_bdeck = (
        "AL, 09, 2005082318,   , BEST,   0, 238N,  757W,  30, 1008, TD\n"
        "AL, 09, 2005082400,   , BEST,   0, 242N,  763W,  30, 1007, TD\n"
    )
    respx.get("https://ftp.nhc.noaa.gov/atcf/btk/bal092005.dat").mock(
        return_value=httpx.Response(200, text=sample_bdeck)
    )

    text = await client.get_best_track_atcf("al", 9, 2005)
    assert "238N" in text
    assert "BEST" in text


@respx.mock
@pytest.mark.asyncio
async def test_get_best_track_atcf_404(client):
    """Test handling of missing ATCF B-deck file."""
    respx.get("https://ftp.nhc.noaa.gov/atcf/btk/bal992099.dat").mock(
        return_value=httpx.Response(404)
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.get_best_track_atcf("al", 99, 2099)


@respx.mock
@pytest.mark.asyncio
async def test_get_hurdat2(client):
    """Test fetching HURDAT2 data with caching."""
    sample = "AL092005,            KATRINA,     1,\n20050823, 1800,  , TD, 238N,  757W,  30, 1008\n"
    respx.get(HURDAT2_URLS["al"]).mock(return_value=httpx.Response(200, text=sample))

    text1 = await client.get_hurdat2("al")
    assert "KATRINA" in text1

    # Second call should use cache (no new HTTP request)
    text2 = await client.get_hurdat2("al")
    assert text1 == text2
    # respx only recorded one call
    assert respx.calls.call_count == 1


@respx.mock
@pytest.mark.asyncio
async def test_get_hurdat2_cp_falls_back_to_ep(client):
    """Test that 'cp' basin falls back to 'ep' HURDAT2 file."""
    sample = "EP042023, SOME_STORM, 1,\n20230901, 0000,  , TD, 150N, 1500W, 25, 1005\n"
    respx.get(HURDAT2_URLS["ep"]).mock(return_value=httpx.Response(200, text=sample))

    text = await client.get_hurdat2("cp")
    assert "SOME_STORM" in text


@respx.mock
@pytest.mark.asyncio
async def test_query_arcgis_layer(client):
    """Test querying ArcGIS MapServer."""
    mock_response = {
        "features": [
            {
                "attributes": {
                    "stormname": "KATRINA",
                    "tau": 0,
                    "maxwind": 150,
                },
                "geometry": {"x": -89.0, "y": 27.0},
            }
        ]
    }
    respx.get(url__startswith=ARCGIS_BASE_URL).mock(
        return_value=httpx.Response(200, json=mock_response)
    )

    data = await client.query_arcgis_layer(6)
    assert len(data["features"]) == 1
    assert data["features"][0]["attributes"]["stormname"] == "KATRINA"


@respx.mock
@pytest.mark.asyncio
async def test_query_arcgis_layer_error(client):
    """Test handling of ArcGIS error response."""
    mock_error = {"error": {"code": 400, "message": "Invalid layer"}}
    respx.get(url__startswith=ARCGIS_BASE_URL).mock(
        return_value=httpx.Response(200, json=mock_error)
    )

    with pytest.raises(NHCAPIError, match="Invalid layer"):
        await client.query_arcgis_layer(999)


@respx.mock
@pytest.mark.asyncio
async def test_get_hurdat2_invalid_basin(client):
    """Test that invalid basin raises ValueError."""
    with pytest.raises(ValueError, match="No HURDAT2 data available"):
        await client.get_hurdat2("xx")


@respx.mock
@pytest.mark.asyncio
async def test_client_close_idempotent(client):
    """Test that closing an already-closed client doesn't error."""
    await client.close()
    await client.close()  # Should not raise


# ---------------------------------------------------------------------------
# HURDAT2 URL resolution (regression: client hard-coded the 2024 archive file
# so every new season was silently missing. The URL is now discovered from
# the NHC data index — newest season — with a graceful fallback.)
# ---------------------------------------------------------------------------

# Two AL files on the index: an older 2024 and the current 2025. The resolver
# must pick 2025, not whichever appears first.
_INDEX_HTML = """<html><body>
<a href="/data/hurdat/hurdat2-1851-2024-040425.txt">atl 2024</a>
<a href="/data/hurdat/hurdat2-1851-2025-02272026.txt">atl 2025</a>
<a href="/data/hurdat/hurdat2-nepac-1949-2025-02272026.txt">nepac 2025</a>
</body></html>"""


@respx.mock
@pytest.mark.asyncio
async def test_hurdat2_url_resolves_newest_year(client):
    """Resolver picks the newest 'data-through' year, not the 2024 file."""
    respx.get(HURDAT2_INDEX_URL).mock(
        return_value=httpx.Response(200, text=_INDEX_HTML)
    )
    url = await client._resolve_hurdat2_url("al")
    assert url.endswith("/data/hurdat/hurdat2-1851-2025-02272026.txt")

    ep = await client._resolve_hurdat2_url("ep")
    assert ep.endswith("/data/hurdat/hurdat2-nepac-1949-2025-02272026.txt")


@respx.mock
@pytest.mark.asyncio
async def test_hurdat2_url_falls_back_on_index_failure(client):
    """If the index is unreachable, fall back to the known-good constant —
    discovery must never make the tool fail when a usable URL is known."""
    respx.get(HURDAT2_INDEX_URL).mock(return_value=httpx.Response(503))
    url = await client._resolve_hurdat2_url("al")
    assert url == HURDAT2_URLS["al"]


@respx.mock
@pytest.mark.asyncio
async def test_get_hurdat2_uses_resolved_url_and_caches(client):
    """get_hurdat2 fetches the discovered URL and caches the body."""
    resolved = "https://www.nhc.noaa.gov/data/hurdat/hurdat2-1851-2025-02272026.txt"
    respx.get(HURDAT2_INDEX_URL).mock(
        return_value=httpx.Response(200, text=_INDEX_HTML)
    )
    body_route = respx.get(resolved).mock(
        return_value=httpx.Response(200, text="HEADER\nAL122005,...")
    )

    text = await client.get_hurdat2("al")
    assert text.startswith("HEADER")

    # Second call served from cache — no extra HTTP to the data file.
    text2 = await client.get_hurdat2("al")
    assert text2 == text
    assert body_route.call_count == 1


@respx.mock
@pytest.mark.asyncio
async def test_get_hurdat2_cp_maps_to_ep(client):
    """'cp' (Central Pacific) resolves via the East Pacific nepac file."""
    ep_url = "https://www.nhc.noaa.gov/data/hurdat/hurdat2-nepac-1949-2025-02272026.txt"
    respx.get(HURDAT2_INDEX_URL).mock(
        return_value=httpx.Response(200, text=_INDEX_HTML)
    )
    respx.get(ep_url).mock(return_value=httpx.Response(200, text="EP BODY"))
    text = await client.get_hurdat2("cp")
    assert text == "EP BODY"


@respx.mock
@pytest.mark.asyncio
async def test_hurdat2_cache_expires_and_rediscovers_reissue(client):
    """Past the TTL, a long-running process must re-resolve the index and
    pick up an annual reissue under a *new* filename — not serve the stale
    body forever (the non-blocking caveat from PR #45)."""
    old_file = "/data/hurdat/hurdat2-1851-2024-040425.txt"
    new_file = "/data/hurdat/hurdat2-1851-2026-02272027.txt"
    old_url = f"https://www.nhc.noaa.gov{old_file}"
    new_url = f"https://www.nhc.noaa.gov{new_file}"

    # Index returns the 2024 file first, then a 2026 reissue on the next look.
    respx.get(HURDAT2_INDEX_URL).mock(
        side_effect=[
            httpx.Response(200, text=f'<a href="{old_file}">old</a>'),
            httpx.Response(200, text=f'<a href="{new_file}">new</a>'),
        ]
    )
    respx.get(old_url).mock(return_value=httpx.Response(200, text="HURDAT2 2024"))
    respx.get(new_url).mock(return_value=httpx.Response(200, text="HURDAT2 2026"))

    first = await client.get_hurdat2("al")
    assert first == "HURDAT2 2024"

    # Within TTL: served from cache, index/body not hit again.
    again = await client.get_hurdat2("al")
    assert again == "HURDAT2 2024"

    # Force expiry → re-resolve (new filename) + refetch.
    client._hurdat2_cache_time["al"] = time.time() - (HURDAT2_CACHE_TTL_S + 1)
    refreshed = await client.get_hurdat2("al")
    assert refreshed == "HURDAT2 2026"
