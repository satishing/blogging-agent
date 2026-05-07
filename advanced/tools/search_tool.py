from __future__ import annotations

import json
import re
import time
from datetime import date
from typing import Any

import requests
from crewai.tools import BaseTool
from pydantic import PrivateAttr

from advanced.config import Settings


class SerperSearchClient:
    """HTTP transport for the Serper Google Search API with retry/backoff.

    Returns normalized `{title, url, snippet, published_date}` dicts. Results
    without an extractable year are dropped so they cannot slip past the
    freshness cutoff downstream in CrewService.
    """

    def __init__(self, settings: Settings):
        self._settings = settings

    def search(self, query: str, *, max_results: int | None = None) -> list[dict[str, Any]]:
        payload = {"q": query, "num": max_results or self._settings.search_result_count}
        headers = {
            "X-API-KEY": self._settings.serper_api_key,
            "Content-Type": "application/json",
        }

        response_json = self._post_with_retry(payload=payload, headers=headers)
        organic = response_json.get("organic", [])
        normalized = (self._normalize_result(item) for item in organic)
        return [item for item in normalized if item is not None]

    def _post_with_retry(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
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
        # Drop undated results: stamping them with date.today() previously made
        # stale articles slip past the freshness cutoff in CrewService.
        published_date = SerperSearchClient._extract_date(item.get("date", ""))
        if published_date is None:
            return None
        return {
            "title": item.get("title") or "Untitled Source",
            "url": item.get("link") or "",
            "snippet": item.get("snippet") or "",
            "published_date": published_date.isoformat(),
        }

    @staticmethod
    def _extract_date(raw_value: str) -> date | None:
        # The 20\d{2} pattern matches years 2000-2099. Sufficient for current
        # use; revisit if blogging persists into the year 2100.
        year_match = re.search(r"(20\d{2})", raw_value or "")
        if year_match:
            return date(int(year_match.group(1)), 1, 1)
        return None


class SerperSearchTool(BaseTool):
    name: str = "search_latest_sources"
    description: str = (
        "Searches the web for recent topic coverage and returns dated source objects "
        "with title, url, snippet, and published_date. Undated results are dropped."
    )

    _client: SerperSearchClient = PrivateAttr()

    def __init__(self, settings: Settings, **kwargs: Any):
        super().__init__(**kwargs)
        self._client = SerperSearchClient(settings=settings)

    def _run(self, query: str) -> str:
        results = self._client.search(query)
        return json.dumps(results, ensure_ascii=False)
