"""Editor agent — production version of demo/05_editor_agent.ipynb."""

from crewai import Agent, LLM


def build_editor_agent(llm: LLM) -> Agent:
    return Agent(
        role="Technical Blog Editor",
        goal=(
            "Transform draft content into strict structured JSON and enforce quality standards "
            "for AI learner audiences."
        ),
        backstory=(
            "You validate clarity, source coverage, and output format correctness. "
            "You are strict about schema compliance."
        ),
        llm=llm,
        verbose=False,
    )