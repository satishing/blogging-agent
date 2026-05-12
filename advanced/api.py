"""FastAPI factory + request/response models for the blogging agent service."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from advanced.config import get_settings
from advanced.runtime import run_pipeline
from advanced.security import InMemoryRateLimiter, hash_bucket_key
from advanced.utils import setup_logging


class GenerateBlogRequest(BaseModel):
    topic: str = Field(min_length=3)
    publish: bool = False
    force_refresh: bool = False
    min_year: int | None = None


class GenerateBlogResponse(BaseModel):
    status: str
    result: dict[str, Any]


def create_app():
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse

    settings = get_settings()
    setup_logging(settings.log_level, f"{settings.log_dir}/app.log")

    if settings.api_auth_enabled and not settings.api_auth_key:
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

    @app.middleware("http")
    async def api_security_middleware(request, call_next):
        if request.url.path in exempt_paths:
            return await call_next(request)

        if settings.api_auth_enabled:
            provided = request.headers.get(settings.api_auth_header_name)
            if provided != settings.api_auth_key:
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            identifier = hash_bucket_key(provided)
        else:
            identifier = request.client.host if request.client else "anonymous"

        if settings.api_rate_limit_enabled:
            allowed, retry_after, remaining = rate_limiter.check(identifier)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={"Retry-After": str(retry_after)},
                )

        response = await call_next(request)
        if settings.api_rate_limit_enabled:
            response.headers["X-RateLimit-Limit"] = str(
                settings.api_rate_limit_per_minute
            )
            response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/v1/blogs/generate", response_model=GenerateBlogResponse)
    def generate_blog(payload: GenerateBlogRequest) -> GenerateBlogResponse:
        try:
            result = run_pipeline(
                topic=payload.topic,
                publish=payload.publish,
                force_refresh=payload.force_refresh,
                min_year=payload.min_year,
            )
            return GenerateBlogResponse(status="success", result=result)
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error

    return app
