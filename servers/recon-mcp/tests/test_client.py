"""Tests for ReconClient using respx-mocked HTTP responses."""

import pytest
import httpx
import respx

from recon_mcp.client import ReconClient


@pytest.fixture
async def client():
    c = ReconClient()
    yield c
    await c.close()


@respx.mock
@pytest.mark.asyncio
async def test_fetch_text(client):
    url = "https://www.nhc.noaa.gov/archive/recon/2024/test.txt"
    respx.get(url).mock(return_value=httpx.Response(200, text="hello world"))

    result = await client.fetch_text(url)
    assert result == "hello world"


@respx.mock
@pytest.mark.asyncio
async def test_fetch_text_404(client):
    url = "https://www.nhc.noaa.gov/archive/recon/2024/missing.txt"
    respx.get(url).mock(return_value=httpx.Response(404))

    with pytest.raises(httpx.HTTPStatusError):
        await client.fetch_text(url)


@respx.mock
@pytest.mark.asyncio
async def test_list_directory(client):
    url = "https://www.nhc.noaa.gov/archive/recon/2024/AHONT1/"
    html = '<html><body><a href="file1.txt">file1.txt</a></body></html>'
    respx.get(url).mock(return_value=httpx.Response(200, text=html))

    result = await client.list_directory(url)
    assert "file1.txt" in result


@respx.mock
@pytest.mark.asyncio
async def test_list_directory_adds_slash(client):
    """list_directory adds trailing slash if missing."""
    url_without_slash = "https://www.nhc.noaa.gov/archive/recon/2024/AHONT1"
    url_with_slash = url_without_slash + "/"
    respx.get(url_with_slash).mock(
        return_value=httpx.Response(200, text="<html></html>")
    )

    result = await client.list_directory(url_without_slash)
    assert result == "<html></html>"


def test_build_archive_dir_url(client):
    url = client.build_archive_dir_url(2024, "hdob", "al")
    assert url == "https://www.nhc.noaa.gov/archive/recon/2024/AHONT1/"


def test_build_archive_dir_url_ep(client):
    url = client.build_archive_dir_url(2024, "hdob", "ep")
    assert url == "https://www.nhc.noaa.gov/archive/recon/2024/AHOPN1/"


def test_build_archive_dir_url_vdm(client):
    url = client.build_archive_dir_url(2024, "vdm", "al")
    assert url == "https://www.nhc.noaa.gov/archive/recon/2024/REPNT2/"


def test_build_archive_dir_url_cp_fallback(client):
    """CP basin falls back to EP directory."""
    url = client.build_archive_dir_url(2024, "hdob", "cp")
    assert url == "https://www.nhc.noaa.gov/archive/recon/2024/AHOPN1/"


def test_build_archive_dir_url_invalid():
    c = ReconClient()
    with pytest.raises(ValueError, match="No archive directory"):
        c.build_archive_dir_url(2024, "invalid", "al")


def test_build_atcf_fdeck_url(client):
    url = client.build_atcf_fdeck_url("al", 14, 2024)
    assert url == "https://ftp.nhc.noaa.gov/atcf/fix/fal142024.dat"


def test_build_atcf_fdeck_url_padded(client):
    url = client.build_atcf_fdeck_url("ep", 5, 2023)
    assert url == "https://ftp.nhc.noaa.gov/atcf/fix/fep052023.dat"


@pytest.mark.asyncio
async def test_close_idempotent():
    """Closing a client that was never used should not raise."""
    c = ReconClient()
    await c.close()
    await c.close()  # Should not raise
