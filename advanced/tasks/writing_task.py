"""Writing task — production version of demo/04_content_writer_agent.ipynb."""

from crewai import Agent, Task


def build_writing_task(agent: Agent) -> Task:
    return Task(
        description=(
            "Use the research JSON below to write a technical educational blog for "
            "AI learners. The blog should be actionable and include examples, but "
            "avoid unsupported claims and only rely on the provided sources.\n\n"
            "Research JSON:\n{research_json}"
        ),
        expected_output="Markdown blog draft with sections and clear explanations.",
        agent=agent,
    )
