"""Dual-purpose client: local file reader + ADCIRC wiki documentation fetcher."""

import re

import httpx

ADCIRC_WIKI_BASE = "https://wiki.adcirc.org"
WIKI_API_URL = f"{ADCIRC_WIKI_BASE}/w/api.php"

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


class ADCIRCClientError(Exception):
    """Custom exception for ADCIRC client errors."""

    pass


class ADCIRCClient:
    """Async client for local file reading and ADCIRC wiki access."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
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
                f"Wiki page not found: {data['error'].get('info', page_title)}"
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
