"""FastAPI factory + request/response models for the blogging agent service."""

from __future__ import annotations

import hmac
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from advanced.config import get_settings, reveal
from advanced.runtime import run_pipeline
from advanced.security import InMemoryRateLimiter, hash_bucket_key
from advanced.services import SourceGuardrailError
from advanced.utils import get_logger, setup_logging

logger = get_logger(__name__)

# Documented for OpenAPI so the error contract is explicit (SonarQube: every
# raised HTTPException status must appear in the route's `responses`).
_GENERATE_RESPONSES: dict[int | str, dict[str, Any]] = {
    422: {
        "description": (
            "Content guardrails could not be satisfied "
            "(e.g. too few fresh sources for the topic)."
        )
    },
    500: {
        "description": (
            "Unexpected internal error. The body contains a correlation id "
            "to quote when reporting the problem; no internal details are leaked."
        )
    },
}


class GenerateBlogRequest(BaseModel):
    topic: str = Field(min_length=3)
    publish: bool = False
    force_refresh: bool = False
    min_year: int | None = None


class GenerateBlogResponse(BaseModel):
    status: str
    result: dict[str, Any]


def _is_authorized(provided: str | None, api_auth_key: str) -> bool:
    return bool(provided) and hmac.compare_digest(provided, api_auth_key)


def _client_identifier(request, settings, api_auth_key: str) -> str | None:
    """Return a rate-limit identifier for the request, or None if unauthorized."""
    if not settings.api_auth_enabled:
        return request.client.host if request.client else "anonymous"
    provided = request.headers.get(settings.api_auth_header_name)
    if not _is_authorized(provided, api_auth_key):
        return None
    return hash_bucket_key(provided)


def _build_security_middleware(settings, rate_limiter, api_auth_key, exempt_paths):
    """Build the auth + rate-limit middleware as a closure over app config."""
    from fastapi.responses import JSONResponse

    async def api_security_middleware(request, call_next):
        if request.url.path in exempt_paths:
            return await call_next(request)

        identifier = _client_identifier(request, settings, api_auth_key)
        if identifier is None:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        remaining: int | None = None
        if settings.api_rate_limit_enabled:
            allowed, retry_after, remaining = rate_limiter.check(identifier)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={"Retry-After": str(retry_after)},
                )

        response = await call_next(request)
        if remaining is not None:
            response.headers["X-RateLimit-Limit"] = str(
                settings.api_rate_limit_per_minute
            )
            response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    return api_security_middleware


def _generate_blog(payload: GenerateBlogRequest) -> GenerateBlogResponse:
    from fastapi import HTTPException

    try:
        result = run_pipeline(
            topic=payload.topic,
            publish=payload.publish,
            force_refresh=payload.force_refresh,
            min_year=payload.min_year,
        )
        return GenerateBlogResponse(status="success", result=result)
    except SourceGuardrailError as error:
        # Domain failure with a caller-safe message: not enough fresh sources
        # to meet the content guardrails. 422 = understood but unprocessable.
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        # Never echo raw exception text to clients — it can leak internal
        # details. Log the full error server-side under a correlation id the
        # caller can quote when reporting the problem.
        correlation_id = uuid4().hex
        logger.exception("Unhandled error in generate_blog [ref=%s]", correlation_id)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error (ref: {correlation_id})",
        ) from error


def create_app():
    from fastapi import FastAPI

    settings = get_settings()
    setup_logging(settings.log_level, f"{settings.log_dir}/app.log")

    # Resolve the auth secret once at startup; the raw value only lives in this
    # closure, never in request handling beyond a constant-time comparison.
    api_auth_key = reveal(settings.api_auth_key)
    if settings.api_auth_enabled and not api_auth_key:
        raise RuntimeError("API auth is enabled but API_AUTH_KEY is missing.")

    app = FastAPI(title="Blogging Agent API", version="1.0.0")
    rate_limiter = InMemoryRateLimiter(
        max_requests=settings.api_rate_limit_per_minute,
        window_seconds=settings.api_rate_limit_window_seconds,
    )
    exempt_paths = {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/docs/oauth2-redirect",
        "/favicon.ico",
    }

    app.middleware("http")(
        _build_security_middleware(settings, rate_limiter, api_auth_key, exempt_paths)
    )
    app.get("/health")(_health)
    app.post("/v1/blogs/generate", responses=_GENERATE_RESPONSES)(_generate_blog)
    return app


def _health() -> dict:
    return {"status": "ok"}
