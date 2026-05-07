"""Publisher agent — production version of Demo/06_publish_agent.ipynb."""

from crewai import Agent, LLM


def build_publisher_agent(llm: LLM, publish_tool) -> Agent:
    return Agent(
        role="Publisher Operations Agent",
        goal="Publish validated blog payloads to content platforms and return exact publish metadata.",
        backstory=(
            "You are precise and operationally careful. You only publish validated inputs "
            "and report canonical response identifiers."
        ),
        llm=llm,
        tools=[publish_tool],
        verbose=False,
    )
