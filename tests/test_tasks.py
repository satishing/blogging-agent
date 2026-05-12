from crewai import LLM

from advanced.agents import build_editor_agent, build_research_agent, build_writer_agent
from advanced.config.settings import Settings
from advanced.tasks import build_editing_task, build_research_task, build_writing_task
from advanced.tools import SerperSearchTool


def _test_llm() -> LLM:
    return LLM(
        model="openai/gpt-4o", base_url="https://openrouter.ai/api/v1", api_key="test"
    )


def _test_settings() -> Settings:
    return Settings(
        OPENROUTER_API_KEY="test",
        SERPER_API_KEY="test",
        DEVTO_API_KEY="test",
        cache_backend="file",
    )


def test_task_factories_include_expected_guardrail_prompts() -> None:
    llm = _test_llm()
    settings = _test_settings()
    search_tool = SerperSearchTool(settings=settings)

    research_agent = build_research_agent(llm, search_tool)
    writer_agent = build_writer_agent(llm)
    editor_agent = build_editor_agent(llm)

    research_task = build_research_task(research_agent, min_year=2026, min_sources=4)
    writing_task = build_writing_task(writer_agent, research_task)
    editing_task = build_editing_task(
        editor_agent,
        writing_task,
        min_read_minutes=6,
        max_read_minutes=8,
    )

    assert "2026 onward" in research_task.description
    assert "strict JSON" in editing_task.description
    assert writing_task.context and len(writing_task.context) == 1
