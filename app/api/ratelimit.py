"""Per-client token bucket for expensive endpoints (each /ask can call the LLM several times).

In-process only: fine for the single-server deployment, not shared across processes.
The client key is the X-Forwarded-For first hop when behind the Caddy proxy, else the peer IP.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from fastapi import HTTPException, Request

from app.core.config import get_settings


class TokenBucket:
    def __init__(self, per_minute: float, burst: int | None = None,
                 clock: Callable[[], float] = time.monotonic):  # fmt: skip
        self.rate = per_minute / 60.0
        self.capacity = float(burst or max(1, int(per_minute)))
        self.clock = clock
        self._state: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def take(self, key: str) -> float:
        """Take one token. Returns 0 if allowed, else seconds until a token is available."""
        with self._lock:
            now = self.clock()
            tokens, last = self._state.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last) * self.rate)
            if tokens >= 1:
                self._state[key] = (tokens - 1, now)
                return 0.0
            self._state[key] = (tokens, now)
            return (1 - tokens) / self.rate if self.rate > 0 else 60.0


_bucket: TokenBucket | None = None


def bucket() -> TokenBucket:
    global _bucket
    if _bucket is None:
        _bucket = TokenBucket(get_settings().rate_limit_per_min)
    return _bucket


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limited(request: Request) -> None:
    wait = bucket().take(client_key(request))
    if wait > 0:
        raise HTTPException(
            status_code=429,
            detail="too many requests, slow down",
            headers={"Retry-After": str(max(1, int(wait + 0.999)))},
        )
