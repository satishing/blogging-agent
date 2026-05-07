"""Editing task — production version of Demo/05_editor_agent.ipynb."""

from crewai import Agent, Task


def build_editing_task(
    agent: Agent,
    writing_task: Task,
    *,
    min_read_minutes: int,
    max_read_minutes: int,
) -> Task:
    return Task(
        description=(
            "Convert the markdown blog into strict JSON. "
            "JSON keys required: topic, title, summary, content_markdown, tags, estimated_read_minutes, sources. "
            f"estimated_read_minutes must be between {min_read_minutes} and {max_read_minutes}. "
            "sources must include title, url, published_date, evidence."
        ),
        expected_output=(
            '{"topic":"...","title":"...","summary":"...","content_markdown":"...",'
            '"tags":["ai"],"estimated_read_minutes":7,'
            '"sources":[{"title":"...","url":"https://...","published_date":"YYYY-MM-DD","evidence":"..."}]}'
        ),
        agent=agent,
        context=[writing_task],
    )