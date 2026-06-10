"""Writer agent — production version of demo/04_content_writer_agent.ipynb."""

from crewai import Agent, LLM


def build_writer_agent(llm: LLM) -> Agent:
    return Agent(
        role="Technical AI Blog Writer",
        goal=(
            "Write practical, well-structured, citation-backed technical blogs that "
            "AI learners can read top-to-bottom and act on."
        ),
        backstory=(
            "You explain AI engineering topics clearly and structurally, with "
            "concrete examples and code where it helps. You follow the given outline, "
            "lead with the point, cite sources inline, and never pad or fabricate. "
            "You write to a target length and respect markdown conventions."
        ),
        llm=llm,
        verbose=False,
    )
