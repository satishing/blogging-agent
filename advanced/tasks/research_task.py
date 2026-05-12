"""Research task — production version of demo/03_research_agent_with_tool.ipynb."""

from crewai import Agent, Task


def build_research_task(agent: Agent, *, min_year: int, min_sources: int) -> Task:
    return Task(
        description=(
            "Research the topic '{topic}' with a web search tool. "
            f"Focus on sources from {min_year} onward. Include at least {min_sources} dated sources. "
            "Return strict JSON with fields: topic, key_points (list), "
            "sources (list of objects with title, url, published_date, evidence)."
        ),
        expected_output=(
            '{"topic":"...","key_points":["..."],'
            '"sources":[{"title":"...","url":"https://...","published_date":"YYYY-MM-DD","evidence":"..."}]}'
        ),
        agent=agent,
    )
