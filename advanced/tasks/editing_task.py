"""Editing task — production version of demo/05_editor_agent.ipynb.

The editor does real editorial work (clarity, flow, citation coverage, length)
and then serializes the result into a validated BlogDraft via `output_pydantic`,
which lets CrewAI enforce the schema and retry the agent on malformed output.
"""

from crewai import Agent, Task

from advanced.models import BlogDraft


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
            "- Verify every inline [n] citation resolves to an entry in the "
            "References list, and that claims are actually supported by the "
            "sources. Remove or soften any unsupported claim.\n"
            f"- Keep the read time between {min_read_minutes} and "
            f"{max_read_minutes} minutes; trim padding rather than dropping "
            "substance.\n"
            "- Do not add new facts or sources beyond those provided.\n\n"
            "Then output the final article as JSON with keys: topic, title, "
            "summary, content_markdown (the full edited markdown), tags, "
            "estimated_read_minutes, sources. 'summary' is a 1-2 sentence dek; "
            "'tags' are 2-4 lowercase topic tags; each source keeps its title, "
            "url, published_date, and evidence."
        ),
        expected_output=(
            "A JSON object with fields topic, title, summary, content_markdown, "
            "tags, estimated_read_minutes, and sources — the polished, "
            "citation-consistent final article."
        ),
        agent=agent,
        context=[writing_task],
        output_pydantic=BlogDraft,
    )
