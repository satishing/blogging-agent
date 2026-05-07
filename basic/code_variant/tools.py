"""Custom CrewAI tool: publish a blog JSON to Dev.to as a draft.

A `BaseTool` subclass is the canonical way to give an agent a custom action.
The tool name + description appear in the agent's prompt, so the LLM knows
when (and how) to call it. The `_run` method is the tool's actual behavior.

This is the "basic" version — no idempotency, no retries. See
`advanced/tools/devto_publisher.py` for the production version.
"""

import json
import os

import requests
from crewai.tools import BaseTool


class DevToPublishTool(BaseTool):
    name: str = "publish_to_devto"
    description: str = (
        "Publish a blog post to Dev.to. Input must be a JSON object with "
        "title (string), tags (list of short strings), and content (markdown)."
    )

    def _run(self, article_json: str) -> str:
        api_key = os.environ["DEVTO_API_KEY"]
        article = json.loads(article_json)

        response = requests.post(
            "https://dev.to/api/articles",
            json={
                "article": {
                    "title": article["title"],
                    "body_markdown": article["content"],
                    "tags": article["tags"],
                    "published": False,  # draft-first
                }
            },
            headers={"api-key": api_key, "Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        return response.text
