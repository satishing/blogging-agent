from __future__ import annotations

import json
from json import JSONDecoder


def _strip_fences(text: str) -> str:
    return text.strip().replace("```json", "").replace("```", "").strip()


def extract_json_object(text: str) -> dict:
    """Extract the first valid JSON object from arbitrary text.

    LLM output frequently arrives wrapped in code fences, prefixed by chatty
    preambles, or followed by trailing commentary. We use `JSONDecoder.raw_decode`
    rather than `json.loads` because `raw_decode` parses one JSON value out of
    a longer string — exactly the shape of typical model output.
    """
    cleaned = _strip_fences(text)
    decoder = JSONDecoder()

    for index, char in enumerate(cleaned):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(cleaned[index:])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            continue

    raise ValueError("Could not extract a valid JSON object from text output.")


def estimate_read_minutes(content_markdown: str, words_per_minute: int = 220) -> int:
    words = len(content_markdown.split())
    if words == 0:
        return 0
    return max(1, round(words / words_per_minute))
