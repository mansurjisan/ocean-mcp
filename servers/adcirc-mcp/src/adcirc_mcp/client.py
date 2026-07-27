"""Dual-purpose client: local file reader + ADCIRC wiki documentation fetcher."""

import asyncio
import random
import re
from typing import Any

import httpx

ADCIRC_WIKI_BASE = "https://wiki.adcirc.org"
# The MediaWiki API moved from /w/api.php (now 404) to /api.php. The old path
# silently broke every wiki tool (search + page fetch) with a 404.
WIKI_API_URL = f"{ADCIRC_WIKI_BASE}/api.php"

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


# Transient responses worth retrying: rate-limit + the upstream/gateway 5xx
# family that NOAA endpoints intermittently emit under load.
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


class RetryTransport(httpx.AsyncHTTPTransport):
    """AsyncHTTPTransport that retries idempotent GETs on transient failures.

    httpx's built-in ``retries=`` covers only connection errors; this also
    retries transient HTTP 5xx/429 and timeouts (read included) with
    exponential backoff plus jitter. These servers are read-only and issue
    only GETs, which are safe to replay; non-GET requests and non-transient
    responses pass straight through. Set ``backoff_factor=0`` to retry with
    no delay (used by the test suite).
    """

    def __init__(
        self,
        *args: Any,
        max_retries: int = 2,
        backoff_factor: float = 0.5,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if request.method != "GET":
            return await super().handle_async_request(request)

        last_exc: httpx.TransportError | None = None
        for attempt in range(self._max_retries + 1):
            if attempt:
                delay = self._backoff_factor * (2 ** (attempt - 1))
                await asyncio.sleep(delay + random.uniform(0, delay / 2))
            try:
                response = await super().handle_async_request(request)
            except httpx.TransportError as exc:
                last_exc = exc
                continue
            if response.status_code in _RETRY_STATUS and attempt < self._max_retries:
                await response.aclose()
                continue
            return response
        assert last_exc is not None  # loop ran at least once
        raise last_exc


class ADCIRCClientError(Exception):
    """Custom exception for ADCIRC client errors."""

    pass


def handle_adcirc_error(e: Exception) -> str:
    """Format an exception into a clear, actionable ADCIRC error message.

    Replaces a bare ``f"Error ...: {e}"`` so the caller sees the failure
    category and a concrete next step instead of a raw exception repr.
    """
    if isinstance(e, ADCIRCClientError):
        return f"ADCIRC Error: {e}"
    if isinstance(e, FileNotFoundError):
        return (
            f"ADCIRC Error: file not found ({e.filename or e}). "
            "Check that file_path points to an existing fort.* file."
        )
    if isinstance(e, PermissionError):
        return (
            f"ADCIRC Error: permission denied reading ({e.filename or e}). "
            "Check the file's read permissions and try again."
        )
    if isinstance(e, OSError):
        return (
            f"ADCIRC Error: could not read file — {e}. "
            "Verify file_path is correct and accessible."
        )
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        return (
            f"ADCIRC Error: HTTP {status} fetching the ADCIRC wiki. "
            "The page may not exist — try adcirc_search_docs to find the correct "
            "title, or retry if this is a transient server error."
        )
    if isinstance(e, httpx.TimeoutException):
        return (
            "ADCIRC Error: request to the ADCIRC wiki timed out. "
            "Try again, or narrow the query with adcirc_search_docs."
        )
    return f"ADCIRC Error: {type(e).__name__}: {e}"


class ADCIRCClient:
    """Async client for local file reading and ADCIRC wiki access."""

    def __init__(self, max_retries: int = 2, backoff_factor: float = 0.5) -> None:
        self._client: httpx.AsyncClient | None = None
        self._max_retries = max_retries
        self._backoff_factor = backoff_factor

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                transport=RetryTransport(
                    max_retries=self._max_retries,
                    backoff_factor=self._backoff_factor,
                ),
            )
        return self._client

    @staticmethod
    def read_file(file_path: str) -> str:
        """Read a local file with size limit."""
        import os

        size = os.path.getsize(file_path)
        if size > MAX_FILE_SIZE:
            raise ADCIRCClientError(
                f"File too large ({size / 1024 / 1024:.1f} MB). "
                f"Max is {MAX_FILE_SIZE / 1024 / 1024:.0f} MB."
            )
        with open(file_path) as f:
            return f.read()

    @staticmethod
    def read_file_header(file_path: str, max_lines: int = 100) -> str:
        """Read only the first N lines of a file."""
        lines = []
        with open(file_path) as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                lines.append(line)
        return "".join(lines)

    async def fetch_wiki_page(self, page_title: str) -> str:
        """Fetch a wiki page and return its content as plain text."""
        client = await self._get_client()
        params = {
            "action": "parse",
            "page": page_title,
            "prop": "text",
            "format": "json",
        }
        response = await client.get(WIKI_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise ADCIRCClientError(
                f"Wiki page not found: {data['error'].get('info', page_title)}. "
                "Try adcirc_search_docs to find the correct page title."
            )

        html = data.get("parse", {}).get("text", {}).get("*", "")
        return strip_html_to_text(html)

    async def search_wiki(self, query: str, limit: int = 10) -> list[dict]:
        """Search the ADCIRC wiki and return matching pages."""
        client = await self._get_client()
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": str(limit),
            "format": "json",
        }
        response = await client.get(WIKI_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("query", {}).get("search", []):
            results.append(
                {
                    "title": item.get("title", ""),
                    "snippet": strip_html_to_text(item.get("snippet", "")),
                    "url": f"{ADCIRC_WIKI_BASE}/wiki/{item.get('title', '').replace(' ', '_')}",
                }
            )
        return results

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()


def strip_html_to_text(html: str) -> str:
    """Strip HTML tags and decode entities to plain text."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#039;", "'")
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text
