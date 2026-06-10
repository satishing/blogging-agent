from crewai import LLM

from advanced.agents import build_editor_agent, build_planner_agent, build_writer_agent
from advanced.models import BlogDraft
from advanced.tasks import build_editing_task, build_outline_task, build_writing_task
from advanced.tasks.writing_task import _build_readability_guardrail


def _test_llm() -> LLM:
    return LLM(
        model="openai/gpt-4o", base_url="https://openrouter.ai/api/v1", api_key="test"
    )


def test_task_factories_include_expected_guardrail_prompts() -> None:
    llm = _test_llm()
    planner_agent = build_planner_agent(llm)
    writer_agent = build_writer_agent(llm)
    editor_agent = build_editor_agent(llm)

    outline_task = build_outline_task(planner_agent)
    writing_task = build_writing_task(
        writer_agent, min_words=1320, max_words=1760, min_sources=4
    )
    editing_task = build_editing_task(
        editor_agent,
        writing_task,
        min_read_minutes=6,
        max_read_minutes=8,
    )

    # Outline + writer both consume the deterministically gathered research.
    assert "{research_json}" in outline_task.description
    assert "{research_json}" in writing_task.description
    # Writer spec pins the length band and required structure.
    assert "1320-1760 words" in writing_task.description
    assert "## References" in writing_task.description
    # Editor serializes to a validated BlogDraft via output_pydantic.
    assert editing_task.output_pydantic is BlogDraft


def test_writing_guardrail_enforces_length_structure_and_citations() -> None:
    guardrail = _build_readability_guardrail(min_words=50, max_words=200)

    class _Output:
        def __init__(self, raw: str) -> None:
            self.raw = raw

    # Too short.
    ok, feedback = guardrail(_Output("word " * 10))
    assert ok is False and "too short" in feedback.lower()

    # Long enough but missing required sections / citations.
    body_only = "word " * 120
    ok, feedback = guardrail(_Output(body_only))
    assert ok is False

    # A complete, well-structured draft passes.
    good = (
        "Intro hook sentence that frames the problem clearly for readers. "
        + "word " * 90
        + "\n\n## Key takeaways\n- point\n\n## Background\nText [1].\n\n"
        "## Approach\nMore text.\n\n## Tradeoffs\nMore text.\n\n"
        "## Conclusion\nWrap up.\n\n## References\n1. [Source](https://e.com)\n"
    )
    ok, payload = guardrail(_Output(good))
    assert ok is True
