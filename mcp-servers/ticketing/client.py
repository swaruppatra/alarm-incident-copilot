import asyncio
import logging
import random

import httpx

from .config import get_settings
from .errors import UpstreamError

logger = logging.getLogger("ticketing_mcp.client")

# Retry only transient failures. Never retry a 4xx — a bad token or a bad
# request won't succeed on attempt 2, retrying just wastes time and delays
# the real error reaching the caller.
_RETRYABLE_STATUS_CODES = {500, 502, 503, 504}


class TicketingClient:
    """HTTP client for the Ticketing API simulator — the only place
    timeout/retry/error-mapping/trace-propagation/secret-handling logic
    lives. Every tool calls through here instead of using httpx directly."""

    def __init__(self) -> None:
        settings = get_settings()
        self._token = settings.ticketing_api_token
        self._max_retries = settings.max_retries
        self._client = httpx.AsyncClient(
            base_url=settings.ticketing_api_base_url, timeout=settings.request_timeout_seconds
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json_body: dict | None = None,
        trace_id: str | None = None,
        x_client_id: str | None = None,
        x_metadata_tag: str | None = None,
    ) -> dict:
        """Call the Ticketing API with retry + structured error mapping.

        Args:
            method: HTTP method, e.g. "GET" or "POST".
            path: path relative to the base URL, e.g. "/tickets/search".
            params: query parameters.
            json_body: JSON body for POST/PATCH endpoints.
            trace_id: correlation id to propagate; generated if not supplied.
            x_client_id: optional client id header to propagate.
            x_metadata_tag: optional metadata tag header to propagate.

        Returns:
            dict: the parsed JSON response body.

        Raises:
            UpstreamError: on 401/404/422, or exhausted retries on a
                transient failure.
        """
        # --- trace_id propagation ---
        trace_id = trace_id or f"mcp-{random.getrandbits(32):08x}"
        headers = {"Authorization": f"Bearer {self._token}", "trace_id": trace_id}
        if x_client_id:
            headers["x-client-id"] = x_client_id
        if x_metadata_tag:
            headers["x-metadata-tag"] = x_metadata_tag

        last_exc: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            # --- never log the bearer token: log fields individually,
            # never the `headers` dict itself ---
            logger.info(
                "ticketing_api_request",
                extra={"method": method, "path": path, "attempt": attempt, "trace_id": trace_id},
            )
            try:
                response = await self._client.request(
                    method, path, params=params, json=json_body, headers=headers
                )
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                # --- timeout + retry, network-level failure ---
                last_exc = exc
                logger.warning(
                    "ticketing_api_network_error",
                    extra={"path": path, "attempt": attempt, "trace_id": trace_id, "error": str(exc)},
                )
                await self._backoff(attempt)
                continue

            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self._max_retries:
                # --- timeout + retry, transient server-side failure ---
                logger.warning(
                    "ticketing_api_retryable_status",
                    extra={"path": path, "attempt": attempt, "status_code": response.status_code, "trace_id": trace_id},
                )
                await self._backoff(attempt)
                continue

            return self._handle_response(response, trace_id)

        raise UpstreamError(
            error_type="upstream_unavailable",
            detail=f"Ticketing API unreachable after {self._max_retries} attempts: {last_exc}",
            status_code=None,
            trace_id=trace_id,
        )

    async def _backoff(self, attempt: int) -> None:
        # Exponential backoff: ~0.5s, 1s, 2s, capped at 4s, + jitter so
        # concurrent retrying tool calls don't all retry in lockstep.
        delay = min(0.5 * (2 ** (attempt - 1)), 4.0) + random.uniform(0, 0.1)
        await asyncio.sleep(delay)

    def _handle_response(self, response: httpx.Response, trace_id: str) -> dict:
        if response.status_code < 400:
            return response.json()

        # --- map HTTP errors -> structured MCP errors ---
        error_type = {401: "authentication_error", 404: "not_found", 422: "validation_error"}.get(
            response.status_code, "upstream_error"
        )
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text

        raise UpstreamError(error_type=error_type, detail=str(detail), status_code=response.status_code, trace_id=trace_id)
