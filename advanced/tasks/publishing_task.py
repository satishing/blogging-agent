"""Publishing task — production version of demo/06_publish_agent.ipynb."""

from crewai import Agent, Task


def build_publishing_task(agent: Agent) -> Task:
    return Task(
        description=(
            "Use the publish_to_devto tool exactly once with the blog JSON below. "
            "Return the JSON response from the tool verbatim — no commentary, no extra fields.\n\n"
            "{blog_json}"
        ),
        expected_output=(
            "The exact JSON response from the publish_to_devto tool, "
            "containing platform, status, external_id, and url."
        ),
        agent=agent,
    )
