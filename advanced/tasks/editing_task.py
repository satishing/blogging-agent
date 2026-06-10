"""Editing task — production version of demo/05_editor_agent.ipynb.

The editor does real editorial work (clarity, flow, citation coverage, length)
and serializes the result into a validated `EditedBlog` via `output_pydantic`,
which lets CrewAI enforce the schema and retry the agent on malformed output.

The editor does NOT emit sources: the source list is gathered deterministically
and overridden after generation, and excluding it keeps the response schema free
of the `HttpUrl` (`format: uri`) that OpenAI structured output rejects.
"""

from crewai import Agent, Task

from advanced.models import EditedBlog


def build_editing_task(
    agent: Agent,
    writing_task: Task,
    *,
    min_read_minutes: int,
    max_read_minutes: int,
) -> Task:
    return Task(
        description=(
            "Edit and finalize the drafted blog, then emit it as structured data.\n\n"
            "Editorial pass (improve, don't just reformat):\n"
            "- Tighten wording and fix any awkward phrasing; prefer active voice.\n"
            "- Ensure a logical flow: hook, key takeaways, body sections, "
            "conclusion, references.\n"
            "- Keep the inline [n] citations the writer used; they map to the "
            "numbered sources. Remove or soften any claim not supported by them.\n"
            f"- Keep the read time between {min_read_minutes} and "
            f"{max_read_minutes} minutes; trim padding rather than dropping "
            "substance.\n"
            "- Do not add new facts or sources beyond those provided.\n\n"
            "Then output the final article as JSON with keys: topic, title, "
            "summary, content_markdown (the full edited markdown including its "
            "inline [n] citations), tags, estimated_read_minutes. 'summary' is a "
            "1-2 sentence dek; 'tags' are 2-4 lowercase topic tags. Do NOT include "
            "a sources field — sources are attached automatically."
        ),
        expected_output=(
            "A JSON object with fields topic, title, summary, content_markdown, "
            "tags, and estimated_read_minutes — the polished, citation-consistent "
            "final article (no sources field)."
        ),
        agent=agent,
        context=[writing_task],
        output_pydantic=EditedBlog,
    )
