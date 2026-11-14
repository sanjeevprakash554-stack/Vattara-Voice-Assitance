"""In-memory sliding window rate limiter for FastAPI routes.

Provides IP-based sliding window request throttling to defend against
credential brute-forcing and denial-of-service on sensitive endpoints.
"""

from collections import defaultdict, deque
import threading
import time
from fastapi import HTTPException, Request, status
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SlidingWindowRateLimiter:
    """Thread-safe sliding window rate limiter keyed by client identifier and route."""

    _instances: list["SlidingWindowRateLimiter"] = []
    _lock = threading.Lock()

    def __init__(self, times: int = 5, seconds: int = 60, name: str = "default") -> None:
        self.times = times
        self.seconds = seconds
        self.name = name
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        with SlidingWindowRateLimiter._lock:
            SlidingWindowRateLimiter._instances.append(self)

    def _get_client_ip(self, request: Request) -> str:
        """Extract remote client IP from headers or connection state."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Client IP is the leftmost address in X-Forwarded-For chain
            return forwarded.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "127.0.0.1"

    async def __call__(self, request: Request) -> None:
        """FastAPI dependency callable that checks and enforces rate limits."""
        if not settings.RATE_LIMIT_ENABLED:
            return

        client_ip = self._get_client_ip(request)
        key = f"{self.name}:{client_ip}"
        now = time.time()
        window_start = now - self.seconds

        with SlidingWindowRateLimiter._lock:
            history = self.hits[key]

            # Evict timestamps outside the active sliding window
            while history and history[0] < window_start:
                history.popleft()

            if len(history) >= self.times:
                oldest = history[0]
                retry_after = max(1, int(oldest + self.seconds - now))
                logger.warning(
                    "Rate limit exceeded for %s on %s (%d hits in %ds, limit %d). Retry-After: %ds",
                    client_ip,
                    request.url.path,
                    len(history),
                    self.seconds,
                    self.times,
                    retry_after,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many requests. Please wait {retry_after} seconds before trying again.",
                    headers={"Retry-After": str(retry_after)},
                )

            history.append(now)

    @classmethod
    def reset_all(cls) -> None:
        """Reset hit histories across all limiter instances (used in tests)."""
        with cls._lock:
            for inst in cls._instances:
                inst.hits.clear()
