"""Research agent — production version of demo/03_research_agent_with_tool.ipynb."""

from crewai import Agent, LLM


def build_research_agent(llm: LLM, search_tool) -> Agent:
    return Agent(
        role="Senior Technical Research Analyst",
        goal="Collect fresh, verifiable research for {topic} with latest dates and source URLs.",
        backstory=(
            "You specialize in technical AI research. You prioritize recent facts, add dates, "
            "and avoid unsupported claims."
        ),
        llm=llm,
        tools=[search_tool],
        verbose=False,
    )