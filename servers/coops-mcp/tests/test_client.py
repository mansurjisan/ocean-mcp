"""Tests for COOPSClient with mocked HTTP responses."""

import pytest
import httpx
import respx

from coops_mcp.client import (
    COOPSClient,
    COOPSAPIError,
    DATA_API_BASE,
    METADATA_API_BASE,
    DERIVED_API_BASE,
)


@pytest.fixture
async def client():
    c = COOPSClient()
    yield c
    await c.close()


class TestFetchData:
    @respx.mock
    @pytest.mark.asyncio
    async def test_successful_fetch(self, client):
        respx.get(DATA_API_BASE).mock(
            return_value=httpx.Response(
                200, json={"data": [{"t": "2024-10-01", "v": "1.0"}]}
            )
        )
        result = await client.fetch_data(
            {"station": "8518750", "product": "water_level"}
        )
        assert "data" in result
        assert len(result["data"]) == 1

    @respx.mock
    @pytest.mark.asyncio
    async def test_api_error_in_json(self, client):
        respx.get(DATA_API_BASE).mock(
            return_value=httpx.Response(
                200, json={"error": {"message": "No data found"}}
            )
        )
        with pytest.raises(COOPSAPIError, match="No data found"):
            await client.fetch_data({"station": "0000000", "product": "water_level"})

    @respx.mock
    @pytest.mark.asyncio
    async def test_sets_format_and_application(self, client):
        route = respx.get(DATA_API_BASE).mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        await client.fetch_data({"station": "8518750"})
        request = route.calls.last.request
        assert "format=json" in str(request.url)
        assert "application=coops_mcp" in str(request.url)

    @respx.mock
    @pytest.mark.asyncio
    async def test_http_error(self, client):
        respx.get(DATA_API_BASE).mock(return_value=httpx.Response(500))
        with pytest.raises(httpx.HTTPStatusError):
            await client.fetch_data({"station": "8518750"})


class TestFetchMetadata:
    @respx.mock
    @pytest.mark.asyncio
    async def test_successful_metadata(self, client):
        respx.get(f"{METADATA_API_BASE}/stations.json").mock(
            return_value=httpx.Response(200, json={"stations": [{"id": "8518750"}]})
        )
        result = await client.fetch_metadata("stations.json")
        assert "stations" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_station_detail(self, client):
        respx.get(f"{METADATA_API_BASE}/stations/8518750.json").mock(
            return_value=httpx.Response(
                200, json={"stations": [{"id": "8518750", "name": "The Battery"}]}
            )
        )
        result = await client.fetch_metadata(
            "stations/8518750.json", {"units": "metric"}
        )
        assert result["stations"][0]["name"] == "The Battery"


class TestFetchDerived:
    @respx.mock
    @pytest.mark.asyncio
    async def test_successful_derived(self, client):
        respx.get(f"{DERIVED_API_BASE}/product/sltrends.json").mock(
            return_value=httpx.Response(200, json={"sltrends": [{"sltrend": 2.87}]})
        )
        result = await client.fetch_derived(
            "product/sltrends.json", {"station": "8518750"}
        )
        assert "sltrends" in result


class TestClientLifecycle:
    @pytest.mark.asyncio
    async def test_close(self):
        c = COOPSClient()
        await c._get_client()  # Create the client
        assert c._client is not None
        await c.close()
        assert c._client.is_closed

    @pytest.mark.asyncio
    async def test_close_when_no_client(self):
        c = COOPSClient()
        await c.close()  # Should not raise
