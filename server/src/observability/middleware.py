from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from src.config import settings
from src.observability.context import reset_request_id, set_request_id
from src.observability.metrics import http_requests_in_progress, observe_http_request


logger = logging.getLogger("src.observability.request")

_SENSITIVE_QUERY_KEY_PATTERNS = (
    "access_token",
    "refresh_token",
    "token",
    "password",
    "secret",
    "authorization",
    "cookie",
    "session",
    "api_key",
)


def _sanitize_query_params(request: Request) -> dict[str, list[str]]:
    sanitized: dict[str, list[str]] = {}
    for key, value in request.query_params.multi_items():
        normalized_key = key.lower()
        is_sensitive = any(pattern in normalized_key for pattern in _SENSITIVE_QUERY_KEY_PATTERNS)
        masked_value = "***" if is_sensitive else value
        sanitized.setdefault(key, []).append(masked_value)
    return sanitized


def _resolve_route_path(request: Request) -> str:
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return str(route.path)
    return request.url.path


def _extract_client_ip(request: Request) -> str | None:
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        first_ip = x_forwarded_for.split(",")[0].strip()
        if first_ip:
            return first_ip
    if request.client is not None:
        return request.client.host
    return None


async def request_logging_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    request_token = set_request_id(request_id)

    method = request.method
    raw_path = request.url.path
    in_progress_labels = {"method": method, "path": raw_path}
    http_requests_in_progress.labels(**in_progress_labels).inc()

    started_at = time.perf_counter()
    response: Response | None = None
    error = False
    try:
        response = await call_next(request)
    except Exception:
        error = True
        raise
    finally:
        duration_seconds = time.perf_counter() - started_at
        duration_ms = round(duration_seconds * 1000, 3)

        route_path = _resolve_route_path(request)
        status_code = response.status_code if response is not None else 500
        observe_http_request(
            method=method,
            path=route_path,
            status_code=status_code,
            duration_seconds=duration_seconds,
        )
        http_requests_in_progress.labels(**in_progress_labels).dec()

        user_id = getattr(request.state, "user_id", None)
        log_payload = {
            "event": "http.request",
            "request_id": request_id,
            "method": method,
            "path": route_path,
            "query_params": _sanitize_query_params(request),
            "status_code": status_code,
            "duration_ms": duration_ms,
            "user_id": str(user_id) if user_id is not None else None,
            "client_ip": _extract_client_ip(request),
            "error": error,
        }
        if duration_ms > settings.logging.slow_request_threshold_ms:
            logger.warning("http request completed", extra=log_payload)
        else:
            logger.info("http request completed", extra=log_payload)

        reset_request_id(request_token)

    assert response is not None
    response.headers["X-Request-ID"] = request_id
    return response
