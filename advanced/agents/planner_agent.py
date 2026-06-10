"""Planner agent — drafts the blog outline before the writer drafts prose."""

from crewai import Agent, LLM


def build_planner_agent(llm: LLM) -> Agent:
    return Agent(
        role="Technical Content Strategist",
        goal=(
            "Turn raw research into a tight, logically ordered outline that a writer "
            "can follow to produce a readable, well-structured technical blog."
        ),
        backstory=(
            "You plan educational technical content for AI engineers. You think in "
            "terms of narrative flow: a hook, a promise, progressive sections that "
            "build on each other, and a payoff. You map every planned section to the "
            "research that supports it and never invent facts the sources don't back."
        ),
        llm=llm,
        verbose=False,
    )
