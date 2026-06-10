from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, HttpUrl


class ResearchSource(BaseModel):
    title: str = Field(min_length=4)
    url: HttpUrl
    # Optional: undated sources are kept as a lowest-priority backfill tier by
    # SourceService and rendered as null rather than dropped.
    published_date: date | None = None
    evidence: str = Field(min_length=20)
