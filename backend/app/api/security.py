"""HTTP edge hardening: security headers and in-process API rate limiting.

No extra infrastructure. Limits are per-process sliding windows keyed by client IP.
Health probes are excluded so orchestrators cannot be locked out. Rate limiting is
off in local `development` / `test` unless explicitly enabled.
"""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.core.config import Settings
from app.schemas.common import ErrorDetail, ErrorResponse

_HEALTH_PREFIXES = ("/health", "/api/v1/health")
_EXPENSIVE_MARKERS = (
    "/products/search",
    "/sale-price-prediction",
    "/recommendation",
)

CORS_ALLOW_METHODS = ["GET", "POST", "PATCH", "DELETE", "OPTIONS", "HEAD"]
CORS_ALLOW_HEADERS = [
    "Authorization",
    "Content-Type",
    "Accept",
    "X-Correlation-Id",
    "X-Request-Id",
]


def is_health_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in _HEALTH_PREFIXES)


def is_expensive_path(path: str) -> bool:
    return any(marker in path for marker in _EXPENSIVE_MARKERS)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded[:128]
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


class SlidingWindowLimiter:
    """Thread-safe per-key sliding window. Not a distributed limiter."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window_seconds: float = 60.0) -> bool:
        now = monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True


def validate_runtime_security(settings: Settings) -> None:
    """Fail closed on unsafe production / credentialed-CORS configuration."""
    origins = settings.cors_allowed_origins_list
    if "*" in origins and (settings.cors_allow_credentials or settings.is_production):
        raise ValueError(
            "CORS origin '*' is not allowed when credentials are enabled or the "
            "environment is production."
        )
    if settings.is_production and "changeme" in settings.database_url.lower():
        raise ValueError(
            "Placeholder database credentials are not allowed in production. "
            "Set DATABASE_URL from Key Vault."
        )
    if settings.is_production and settings.clerk_is_configured:
        if not settings.clerk_issuer.strip() or not settings.clerk_audience.strip():
            raise ValueError(
                "CLERK_ISSUER and CLERK_AUDIENCE are required in production when Clerk is configured."
            )


def _safe_validation_fields(errors: list[dict]) -> list[dict]:
    """Return Pydantic error metadata without echoing submitted input values."""
    safe: list[dict] = []
    for item in errors:
        safe.append(
            {
                "type": item.get("type"),
                "loc": item.get("loc"),
                "msg": item.get("msg"),
            }
        )
    return safe


def sanitize_validation_errors(errors: list[dict]) -> list[dict]:
    return _safe_validation_fields(errors)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        response.headers.setdefault("Cache-Control", "no-store")
        if self._settings.is_production:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings
        self._limiter = SlidingWindowLimiter()

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self._settings.rate_limiting_enabled:
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        if is_health_path(path):
            return await call_next(request)

        ip = client_ip(request)
        expensive = is_expensive_path(path)
        limit = (
            self._settings.api_rate_limit_expensive_per_minute
            if expensive
            else self._settings.api_rate_limit_per_minute
        )
        bucket = "expensive" if expensive else "default"
        if not self._limiter.allow(f"{bucket}:{ip}", limit):
            body = ErrorResponse(
                error=ErrorDetail(
                    code="rate_limited",
                    message="Too many requests. Please try again later.",
                )
            )
            return JSONResponse(
                status_code=429,
                content=body.model_dump(mode="json"),
                headers={"Retry-After": "60"},
            )
        return await call_next(request)
