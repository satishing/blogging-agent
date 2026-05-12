from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .research import ResearchSource


class BlogDraft(BaseModel):
    topic: str = Field(min_length=3)
    title: str = Field(min_length=12, max_length=130)
    summary: str = Field(min_length=40)
    content_markdown: str = Field(min_length=500)
    tags: list[str] = Field(default_factory=list)
    estimated_read_minutes: int = Field(ge=1, le=20)
    sources: list[ResearchSource] = Field(default_factory=list)

    @field_validator("tags")
    @classmethod
    def sanitize_tags(cls, value: list[str]) -> list[str]:
        cleaned = [tag.lower().replace(" ", "") for tag in value if tag]
        deduped: list[str] = []
        for tag in cleaned:
            if tag not in deduped:
                deduped.append(tag)
        return deduped[:4] or ["ai", "learning"]


class PublishResult(BaseModel):
    platform: str
    status: str
    external_id: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    raw_response: dict[str, Any] | str | None = None


class PipelineResult(BaseModel):
    topic: str
    blog: BlogDraft
    publish_result: PublishResult | None = None
    cached: bool = False
