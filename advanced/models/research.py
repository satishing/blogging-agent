from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, HttpUrl


class ResearchSource(BaseModel):
    title: str = Field(min_length=4)
    url: HttpUrl
    published_date: date
    evidence: str = Field(min_length=20)
