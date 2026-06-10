from crewai import LLM

from advanced.agents import (
    build_editor_agent,
    build_planner_agent,
    build_writer_agent,
)


def _test_llm() -> LLM:
    return LLM(
        model="openai/gpt-4o", base_url="https://openrouter.ai/api/v1", api_key="test"
    )


def test_agent_factories_create_expected_roles() -> None:
    llm = _test_llm()

    planner = build_planner_agent(llm)
    writer = build_writer_agent(llm)
    editor = build_editor_agent(llm)

    assert "Strategist" in planner.role
    assert "Writer" in writer.role
    assert "Editor" in editor.role
