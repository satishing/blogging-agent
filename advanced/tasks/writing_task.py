"""Writing task — production version of Demo/04_content_writer_agent.ipynb."""

from crewai import Agent, Task


def build_writing_task(agent: Agent, research_task: Task) -> Task:
    return Task(
        description=(
            "Use the research JSON to write a technical educational blog for AI learners. "
            "The blog should be actionable and include examples, but avoid unsupported claims."
        ),
        expected_output="Markdown blog draft with sections and clear explanations.",
        agent=agent,
        context=[research_task],
    )