from __future__ import annotations

import re
import time
from datetime import date, timedelta
from typing import Any

import requests

from advanced.config import Settings


class SerperSearchClient:
    """HTTP transport for the Serper Google Search API with retry/backoff.

    Returns normalized `{title, url, snippet, published_date}` dicts. Undated
    results are kept with `published_date = None` so SourceService can rank them
    as a lowest-priority backfill tier rather than dropping fresh-but-undated
    articles outright.
    """

    def __init__(self, settings: Settings):
        self._settings = settings

    def search(
        self, query: str, *, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        payload = {"q": query, "num": max_results or self._settings.search_result_count}
        headers = {
            "X-API-KEY": self._settings.serper_api_key.get_secret_value(),
            "Content-Type": "application/json",
        }

        response_json = self._post_with_retry(payload=payload, headers=headers)
        organic = response_json.get("organic", [])
        normalized = (self._normalize_result(item) for item in organic)
        return [item for item in normalized if item is not None]

    def _post_with_retry(
        self, payload: dict[str, Any], headers: dict[str, str]
    ) -> dict[str, Any]:
        attempts = 3
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = requests.post(
                    self._settings.serper_api_url,
                    json=payload,
                    headers=headers,
                    timeout=20,
                )
                response.raise_for_status()
                return response.json()
            except requests.RequestException as error:
                last_error = error
                if attempt == attempts:
                    break
                time.sleep(attempt * 1.5)
        raise RuntimeError("Serper search failed after retries") from last_error

    @staticmethod
    def _normalize_result(item: dict[str, Any]) -> dict[str, Any] | None:
        # Keep undated results (published_date=None). SourceService ranks them as
        # a lowest-priority backfill tier, so a fresh-but-undated article is no
        # longer silently discarded the way dropping it here used to do.
        url = item.get("link") or ""
        if not url:
            return None
        published_date = SerperSearchClient._extract_date(item.get("date", ""))
        return {
            "title": item.get("title") or "Untitled Source",
            "url": url,
            "snippet": item.get("snippet") or "",
            "published_date": published_date.isoformat() if published_date else None,
        }

    @staticmethod
    def _extract_date(raw_value: str) -> date | None:
        """Best-effort parse of Serper's free-form `date` field.

        Handles ISO dates (`YYYY-MM-DD` / `YYYY/MM/DD`), relative phrases
        ("today", "yesterday", "N days/weeks/months/years ago"), and a bare-year
        fallback. Returns None when nothing parseable is found.
        """
        value = (raw_value or "").strip().lower()
        if not value:
            return None

        if value == "today":
            return date.today()
        if value == "yesterday":
            return date.today() - timedelta(days=1)

        # ISO-style absolute date with a real month/day.
        iso_match = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", value)
        if iso_match:
            year, month, day = (int(group) for group in iso_match.groups())
            try:
                return date(year, month, day)
            except ValueError:
                return None

        # Relative phrases like "3 days ago" / "2 weeks ago" / "1 month ago".
        relative_match = re.search(r"(\d+)\s+(day|week|month|year)s?\s+ago", value)
        if relative_match:
            amount = int(relative_match.group(1))
            unit = relative_match.group(2)
            unit_to_days = {"day": 1, "week": 7, "month": 30, "year": 365}
            return date.today() - timedelta(days=amount * unit_to_days[unit])

        # Bare-year fallback. The 20\d{2} pattern matches years 2000-2099;
        # revisit if blogging persists into the year 2100.
        year_match = re.search(r"(20\d{2})", value)
        if year_match:
            return date(int(year_match.group(1)), 1, 1)
        return None
