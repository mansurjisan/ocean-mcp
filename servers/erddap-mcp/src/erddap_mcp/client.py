"""Async HTTP client for ERDDAP servers."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import quote, urljoin, urlparse

import httpx

# A caller supplies `server_url` to every tool, so an unguarded client is an
# SSRF primitive: `http://169.254.169.254/` (cloud metadata), `http://localhost`,
# or any RFC1918 address would be fetched. We allow only http(s) to hosts that
# resolve exclusively to public IPs, and re-check every redirect hop.
_MAX_REDIRECTS = 5


class ERDDAPSecurityError(ValueError):
    """Raised when a request URL is blocked by the SSRF guard."""


def _validate_public_http_url(url: str) -> None:
    """Reject non-HTTP(S) schemes and hosts resolving to non-public IPs.

    Raises ERDDAPSecurityError if the URL is unsafe to fetch. DNS is resolved
    and *every* returned address is checked, so a name that resolves to a mix
    of public and private addresses is still rejected.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ERDDAPSecurityError(
            f"Blocked URL scheme {parsed.scheme or '(none)'!r}; "
            f"only http/https are allowed: {url}"
        )
    host = parsed.hostname
    if not host:
        raise ERDDAPSecurityError(f"URL has no host: {url}")
    try:
        infos = socket.getaddrinfo(host, parsed.port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise ERDDAPSecurityError(f"Could not resolve host {host!r}: {e}") from e
    for info in infos:
        addr = info[4][0].split("%")[0]  # strip IPv6 zone id
        ip = ipaddress.ip_address(addr)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise ERDDAPSecurityError(
                f"Blocked request to non-public address {ip} "
                f"(host {host!r}): refusing potential SSRF."
            )


class ERDDAPClient:
    """Async client for ERDDAP REST API."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            # Redirects are followed manually so each hop is SSRF-checked;
            # httpx auto-redirect would let an allowed host bounce us to an
            # internal address.
            self._client = httpx.AsyncClient(
                timeout=60.0,
                follow_redirects=False,
            )
        return self._client

    async def _get_json(self, url: str) -> dict:
        """Fetch a URL and return parsed JSON, handling ERDDAP error responses."""
        client = await self._get_client()
        redirects = 0
        while True:
            _validate_public_http_url(url)
            response = await client.get(url)
            if response.is_redirect and response.headers.get("location"):
                redirects += 1
                if redirects > _MAX_REDIRECTS:
                    raise ERDDAPSecurityError(
                        f"Too many redirects (>{_MAX_REDIRECTS}) starting from {url}"
                    )
                url = urljoin(url, response.headers["location"])
                continue
            break

        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "html" in content_type and "json" not in content_type:
            raise ValueError(
                f"ERDDAP returned HTML instead of JSON. This usually means an error occurred. "
                f"URL: {url}"
            )

        return response.json()

    async def search(
        self,
        server_url: str,
        search_for: str,
        page: int = 1,
        items_per_page: int = 20,
    ) -> dict:
        """Search for datasets on an ERDDAP server.

        Args:
            server_url: Base ERDDAP server URL.
            search_for: Free-text search terms.
            page: Page number (1-indexed).
            items_per_page: Results per page.

        Returns:
            Raw ERDDAP JSON response.
        """
        encoded_search = quote(search_for)
        url = (
            f"{server_url}/search/index.json"
            f"?searchFor={encoded_search}"
            f"&page={page}"
            f"&itemsPerPage={items_per_page}"
        )
        return await self._get_json(url)

    async def get_info(self, server_url: str, dataset_id: str) -> dict:
        """Get dataset metadata/info.

        Args:
            server_url: Base ERDDAP server URL.
            dataset_id: ERDDAP dataset identifier.

        Returns:
            Raw ERDDAP JSON response.
        """
        url = f"{server_url}/info/{dataset_id}/index.json"
        return await self._get_json(url)

    async def get_tabledap(
        self,
        server_url: str,
        dataset_id: str,
        query: str,
    ) -> dict:
        """Fetch data from a tabledap dataset.

        Args:
            server_url: Base ERDDAP server URL.
            dataset_id: ERDDAP dataset identifier.
            query: Pre-built query string (variables & constraints).

        Returns:
            Raw ERDDAP JSON response.
        """
        url = f"{server_url}/tabledap/{dataset_id}.json"
        if query:
            url += f"?{query}"
        return await self._get_json(url)

    async def get_griddap(
        self,
        server_url: str,
        dataset_id: str,
        query: str,
    ) -> dict:
        """Fetch data from a griddap dataset.

        Args:
            server_url: Base ERDDAP server URL.
            dataset_id: ERDDAP dataset identifier.
            query: Pre-built griddap query with bracket notation.

        Returns:
            Raw ERDDAP JSON response.
        """
        url = f"{server_url}/griddap/{dataset_id}.json?{query}"
        return await self._get_json(url)

    async def get_all_datasets(
        self,
        server_url: str,
        query: str = "",
    ) -> dict:
        """List all datasets on an ERDDAP server.

        Args:
            server_url: Base ERDDAP server URL.
            query: Optional query string for filtering.

        Returns:
            Raw ERDDAP JSON response.
        """
        url = f"{server_url}/tabledap/allDatasets.json"
        if query:
            url += f"?{query}"
        return await self._get_json(url)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
