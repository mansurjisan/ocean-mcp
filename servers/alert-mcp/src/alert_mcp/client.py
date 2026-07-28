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
    """Raised when CO-OPS's datagetter responds with an error envelope.

    Verified live against
    https://api.tidesandcurrents.noaa.gov/api/prod/datagetter: CO-OPS uses
    the SAME ``{"error": {"message": "..."}}`` body shape on TWO different
    status codes depending on what's wrong:

    - HTTP 200, when the request is structurally valid but the product
      genuinely isn't offered at that station right now (e.g.
      ``product=air_gap``/``salinity``/``conductivity`` at a station
      lacking that sensor) — message: "No data was found. This product may
      not be offered at this station...".
    - HTTP 400, when the request itself is malformed or invalid (a bad
      ``station`` id, a datum the station doesn't support, or a
      product/station combination CO-OPS rejects outright rather than just
      reporting "not available") — e.g. "Wrong Station ID: Please submit a
      valid station ID" or "There is no MLLW for the station: 9999999".

    Because both cases share the same body shape, the body must be parsed
    and checked for the ``"error"`` key independent of status code —
    checking only after ``raise_for_status()`` (which only 200 survives)
    would silently swallow every HTTP 400 case into a generic
    ``httpx.HTTPStatusError``, discarding the real NOAA diagnostic text.
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

        The body is parsed and checked for CO-OPS's ``{"error": {...}}``
        envelope BEFORE ``raise_for_status()`` runs, since CO-OPS puts that
        same envelope on both HTTP 200 and HTTP 400 responses (see
        ``CoopsAPIError``) — checking after ``raise_for_status()`` would
        never see the body on the 400 path. ``raise_for_status()`` only
        runs once the body has been ruled out as a CO-OPS error envelope, so
        a non-2xx response with some other body shape (e.g. an upstream
        gateway error page) still raises the standard
        ``httpx.HTTPStatusError``.

        Raises:
            CoopsAPIError: If the response body (any status code) carries
                an ``"error"`` key.
            httpx.HTTPError: On transport failures, or a non-2xx status
                whose body isn't the CO-OPS error-envelope shape.
        """
        query = {**params, "format": "json", "application": APPLICATION_NAME}
        client = await self._get_client()
        response = await client.get(COOPS_API_URL, params=query)

        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            raise

        if isinstance(data, dict) and "error" in data:
            message = data["error"].get("message", "Unknown CO-OPS API error")
            raise CoopsAPIError(message.strip())

        response.raise_for_status()
        return data

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
