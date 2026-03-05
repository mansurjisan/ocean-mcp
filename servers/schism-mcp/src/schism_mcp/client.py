"""Dual-purpose client: local file reader + SCHISM documentation fetcher."""

import re

import httpx

SCHISM_DOCS_BASE = "https://schism-dev.github.io/schism"
SCHISM_REPO_URL = "https://raw.githubusercontent.com/schism-dev/schism/master"

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


class SchismClientError(Exception):
    """Custom exception for SCHISM client errors."""

    pass


class SchismClient:
    """Async client for local file reading and SCHISM documentation access."""

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
        known_pages = [
            {
                "title": "Getting Started",
                "path": "getting-started/overview.html",
                "description": "Overview and quick start guide",
            },
            {
                "title": "Input Files",
                "path": "input-output/input-files.html",
                "description": "All SCHISM input files reference",
            },
            {
                "title": "param.nml",
                "path": "input-output/param.nml.html",
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
                "path": "input-output/output-files.html",
                "description": "Output file descriptions",
            },
            {
                "title": "Troubleshooting",
                "path": "getting-started/troubleshooting.html",
                "description": "Common issues and solutions",
            },
            {
                "title": "SCHOUT",
                "path": "input-output/schout.html",
                "description": "SCHISM output control",
            },
            {
                "title": "WWM",
                "path": "modules/wwm.html",
                "description": "Wind Wave Model coupling",
            },
            {
                "title": "SED",
                "path": "modules/sed.html",
                "description": "Sediment transport module",
            },
            {
                "title": "ICM",
                "path": "modules/icm.html",
                "description": "Water quality module",
            },
            {
                "title": "Vertical Grid",
                "path": "mesh-generation/vertical-grid.html",
                "description": "Vertical grid generation",
            },
            {
                "title": "Horizontal Grid",
                "path": "mesh-generation/horizontal-grid.html",
                "description": "Mesh generation guide",
            },
            {
                "title": "Pre-processing",
                "path": "getting-started/pre-processing.html",
                "description": "Pre-processing tools",
            },
            {
                "title": "Hotstart",
                "path": "input-output/hotstart.html",
                "description": "Hot start and restart",
            },
        ]

        results = []
        for page in known_pages:
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
