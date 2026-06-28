from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from app.broker.common import JsonDict, MsxHttpError, query_value
from app.broker.endpoints import Endpoint


@dataclass(slots=True)
class RetryConfig:
    attempts: int = 2
    backoff_seconds: float = 0.2
    retry_statuses: tuple[int, ...] = (429, 500, 502, 503, 504)
    retry_methods: tuple[str, ...] = ("GET",)


class AsyncRateLimiter:
    """Simple process-local minimum-interval limiter."""

    def __init__(self, requests_per_second: float | None = None) -> None:
        self.requests_per_second = requests_per_second
        self._lock = asyncio.Lock()
        self._next_allowed_at = 0.0

    async def wait(self) -> None:
        if not self.requests_per_second or self.requests_per_second <= 0:
            return
        async with self._lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            if now < self._next_allowed_at:
                await asyncio.sleep(self._next_allowed_at - now)
                now = loop.time()
            self._next_allowed_at = now + (1.0 / self.requests_per_second)


class HttpTransport:
    def __init__(
        self,
        base_url: str,
        *,
        timeout: float = 30.0,
        client: httpx.AsyncClient | None = None,
        retry: RetryConfig | None = None,
        rate_limiter: AsyncRateLimiter | None = None,
        max_connections: int = 100,
        max_keepalive_connections: int = 20,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.retry = retry or RetryConfig()
        self.rate_limiter = rate_limiter or AsyncRateLimiter()
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=timeout,
            limits=httpx.Limits(
                max_connections=max_connections,
                max_keepalive_connections=max_keepalive_connections,
            ),
        )

    @property
    def owns_client(self) -> bool:
        return self._owns_client

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def send(
        self,
        endpoint: Endpoint,
        *,
        path: str,
        query: JsonDict,
        body_bytes: bytes | None,
        headers: JsonDict,
    ) -> httpx.Response:
        await self.rate_limiter.wait()
        last_exc: Exception | None = None
        attempts = max(1, self.retry.attempts)
        can_retry = endpoint.method in self.retry.retry_methods
        for attempt in range(1, attempts + 1):
            try:
                response = await self._client.request(
                    endpoint.method,
                    f"{self.base_url}{path}",
                    params=[(key, query_value(query[key])) for key in sorted(query)] or None,
                    content=body_bytes,
                    headers=headers,
                )
                if (
                    not can_retry
                    or response.status_code not in self.retry.retry_statuses
                    or attempt == attempts
                ):
                    return response
            except httpx.HTTPError as exc:
                last_exc = exc
                if not can_retry or attempt == attempts:
                    raise
            await asyncio.sleep(self.retry.backoff_seconds * attempt)
        if last_exc is not None:
            raise last_exc
        raise MsxHttpError(599, endpoint.method, path, "request failed without response")
