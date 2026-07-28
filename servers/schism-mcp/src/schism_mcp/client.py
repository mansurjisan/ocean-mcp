"""Dual-purpose client: local file reader + SCHISM documentation fetcher."""

import asyncio
import random
import re
from typing import Any

import httpx

from .models import SCHISM_DOCS_BASE

SCHISM_REPO_URL = "https://raw.githubusercontent.com/schism-dev/schism/master"

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


class SchismClientError(Exception):
    """Custom exception for SCHISM client errors."""

    pass


# Verified live against https://schism-dev.github.io/schism/master/ (2026-07):
# the docs site restructured under /master/ and dropped or renamed several
# pages the old paths pointed to. Where no dedicated page exists anymore
# (e.g. a "getting started overview" or a standalone "SCHOUT"/output-control
# page), each entry below points to the real page that now documents that
# topic, found by fetching https://schism-dev.github.io/schism/master/ and
# following its nav. Module-level so tests (incl. a live one that walks every
# entry) can exercise it directly, not just through search_docs.
KNOWN_PAGES: list[dict[str, str]] = [
    {
        "title": "Getting Started",
        "path": "index.html",
        "description": "SCHISM manual home page — overview and quick start guide",
    },
    {
        "title": "Input Files",
        "path": "input-output/overview.html",
        "description": "All SCHISM input files reference",
    },
    {
        "title": "param.nml",
        "path": "input-output/param.html",
        "description": "Main parameter namelist reference",
    },
    {
        "title": "hgrid.gr3",
        "path": "input-output/hgrid.html",
        "description": "Horizontal grid format",
    },
    {
        "title": "vgrid.in",
        "path": "input-output/vgrid.html",
        "description": "Vertical grid format",
    },
    {
        "title": "bctides.in",
        "path": "input-output/bctides.html",
        "description": "Tidal boundary condition file",
    },
    {
        "title": "Output Files",
        "path": "input-output/outputs.html",
        "description": "Output file descriptions",
    },
    {
        "title": "Troubleshooting",
        "path": "known_issues.html",
        "description": "Known issues and troubleshooting tips for common problems",
    },
    {
        "title": "SCHOUT",
        "path": "input-output/param.html",
        "description": "SCHISM output control — the &SCHOUT block of param.nml",
    },
    {
        "title": "WWM",
        "path": "modules/wwm.html",
        "description": "Wind Wave Model coupling",
    },
    {
        "title": "2D Sediment Model",
        "path": "modules/sed2d.html",
        "description": "2D sediment transport module",
    },
    {
        "title": "3D Sediment Model",
        "path": "modules/sed3d.html",
        "description": "3D sediment transport module",
    },
    {
        "title": "ICM",
        "path": "modules/icm.html",
        "description": "Water quality module",
    },
    {
        "title": "Vertical Grid",
        "path": "input-output/vgrid.html",
        "description": "Vertical grid generation and format (vgrid.in)",
    },
    {
        "title": "Horizontal Grid",
        "path": "input-output/hgrid.html",
        "description": "Mesh generation guide and horizontal grid format (hgrid.gr3)",
    },
    {
        "title": "Pre-processing",
        "path": "getting-started/pre-processing.html",
        "description": "Pre-processing tools",
    },
    {
        "title": "Hotstart",
        "path": "input-output/optional-inputs.html",
        "description": "Hot start (hotstart.nc) and other optional input files",
    },
]


class SchismClient:
    """Async client for local file reading and SCHISM documentation access."""

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
            raise SchismClientError(
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

    async def fetch_doc_page(self, path: str) -> str:
        """Fetch a documentation page from SCHISM docs site."""
        client = await self._get_client()
        url = f"{SCHISM_DOCS_BASE}/{path}"
        response = await client.get(url)
        response.raise_for_status()
        html = response.text
        return strip_html_to_text(html)

    async def search_docs(self, query: str) -> list[dict]:
        """Search SCHISM documentation by fetching the search index.

        Since SCHISM docs are static (GitHub Pages), we search known page titles.
        """
        query_lower = query.lower()

        results = []
        for page in KNOWN_PAGES:
            score = 0
            for word in query_lower.split():
                if word in page["title"].lower():
                    score += 2
                if word in page["description"].lower():
                    score += 1
            if score > 0:
                results.append(
                    {
                        "title": page["title"],
                        "url": f"{SCHISM_DOCS_BASE}/{page['path']}",
                        "description": page["description"],
                        "score": score,
                    }
                )

        results.sort(key=lambda x: x["score"], reverse=True)
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
