"""Límite de peticiones en memoria (ventana deslizante).

Protege el login contra fuerza bruta y la generación de recetas contra el
abuso de la cuota del LLM. Al correr un solo proceso (WEB_CONCURRENCY=1)
no hace falta un almacenamiento compartido como Redis.
"""

import threading
import time
from collections import defaultdict, deque


class RateLimitExceeded(Exception):
    def __init__(self, retry_after: int):
        super().__init__(f"Límite alcanzado, reintenta en {retry_after} s")
        self.retry_after = retry_after


class RateLimiter:
    def __init__(self, max_calls: int, period_seconds: float) -> None:
        self.max_calls = max_calls
        self.period = period_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> None:
        """Registra una petición; lanza RateLimitExceeded si se superó el límite."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.period:
                hits.popleft()
            if len(hits) >= self.max_calls:
                raise RateLimitExceeded(int(self.period - (now - hits[0])) + 1)
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


login_limiter = RateLimiter(max_calls=10, period_seconds=60)          # por IP y por usuario
register_limiter = RateLimiter(max_calls=5, period_seconds=600)       # por IP
generate_limiter = RateLimiter(max_calls=5, period_seconds=60)        # por usuario
generate_daily_limiter = RateLimiter(max_calls=50, period_seconds=86_400)  # por usuario

ALL_LIMITERS = (login_limiter, register_limiter, generate_limiter, generate_daily_limiter)


def reset_all() -> None:
    for limiter in ALL_LIMITERS:
        limiter.reset()


def enforce(limiter: RateLimiter, key: str, message: str) -> None:
    """Versión para los endpoints: convierte el límite en un HTTP 429."""
    from fastapi import HTTPException

    try:
        limiter.hit(key)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429, detail=message, headers={"Retry-After": str(exc.retry_after)}
        )
