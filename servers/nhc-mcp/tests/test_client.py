"""Mocked HTTP tests for NHCClient using respx."""

import json

import httpx
import pytest
import respx

from nhc_mcp.client import NHCClient, CURRENT_STORMS_URL, HURDAT2_URLS, NHCAPIError
from nhc_mcp.utils import ARCGIS_BASE_URL


@pytest.fixture
async def client():
    c = NHCClient()
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
    respx.get(HURDAT2_URLS["al"]).mock(
        return_value=httpx.Response(200, text=sample)
    )

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
    respx.get(HURDAT2_URLS["ep"]).mock(
        return_value=httpx.Response(200, text=sample)
    )

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
