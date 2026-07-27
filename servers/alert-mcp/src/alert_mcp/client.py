"""Shared async HTTP client for the NOAA CO-OPS datagetter API."""

import asyncio
import random
from typing import Any

import httpx

COOPS_API_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

APPLICATION_NAME = "coral_alert"

# Transient responses worth retrying: rate-limit + the upstream/gateway 5xx
# family that NOAA endpoints intermittently emit under load.
_RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


class RetryTransport(httpx.AsyncHTTPTransport):
    """AsyncHTTPTransport that retries idempotent GETs on transient failures.

    httpx's built-in ``retries=`` covers only connection errors; this also
    retries transient HTTP 5xx/429 and timeouts (read included) with
    exponential backoff plus jitter. This server is read-only and issues
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


class CoopsAPIError(Exception):
    """Raised when CO-OPS's datagetter responds HTTP 200 with an error envelope.

    Verified live against
    https://api.tidesandcurrents.noaa.gov/api/prod/datagetter: a bad
    ``station`` or an unsupported product/station combination returns HTTP
    200 with body ``{"error": {"message": "..."}}`` — ``raise_for_status()``
    never catches this (200 is not an error status), so the parsed body must
    be checked explicitly.
    """


class AlertHTTPClient:
    """Async client for polling the CO-OPS datagetter endpoint.

    Held for the lifetime of the ``AlertManager`` (one client, reused across
    every alert check) rather than opened and closed per check.
    """

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

    async def fetch(self, params: dict[str, Any]) -> dict:
        """Fetch a datagetter JSON response.

        Automatically sets ``format=json`` and ``application``.

        Raises:
            CoopsAPIError: If the response body carries an ``"error"`` key.
            httpx.HTTPError: On transport failures or non-2xx status codes.
        """
        query = {**params, "format": "json", "application": APPLICATION_NAME}
        client = await self._get_client()
        response = await client.get(COOPS_API_URL, params=query)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            message = data["error"].get("message", "Unknown CO-OPS API error")
            raise CoopsAPIError(message.strip())
        return data

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
