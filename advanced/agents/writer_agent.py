"""Writer agent — production version of demo/04_content_writer_agent.ipynb."""

from crewai import Agent, LLM


def build_writer_agent(llm: LLM) -> Agent:
    return Agent(
        role="Technical AI Blog Writer",
        goal="Write practical, educational technical blogs for AI learners.",
        backstory=(
            "You explain AI engineering topics in a clear, structured way with examples, "
            "without oversimplifying core technical concepts."
        ),
        llm=llm,
        verbose=False,
    )