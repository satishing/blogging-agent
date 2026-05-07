"""Agent definitions: role, goal, backstory, LLM, tools.

Four agents matching the end-to-end pipeline:
- `research_agent`  searches the web with Serper.
- `writer_agent`    turns research notes into a Markdown blog post.
- `editor_agent`    converts the Markdown into a publish-ready JSON object.
- `publisher_agent` calls the custom `publish_to_devto` tool to post a draft.

LLM and tool instances are passed in by the caller (built once in `crew.py`)
so we don't construct duplicates per agent.
"""

from crewai import LLM, Agent
from crewai.tools import BaseTool


def research_agent(llm: LLM, search_tool: BaseTool) -> Agent:
    return Agent(
        role="Research Analyst",
        goal="Find recent, verifiable information on {topic}.",
        backstory=(
            "You write short, factual, source-backed summaries. "
            "You always include the URL of every claim you make."
        ),
        llm=llm,
        tools=[search_tool],
        verbose=True,
    )


def writer_agent(llm: LLM) -> Agent:
    return Agent(
        role="Content Writer",
        goal="Write a clear blog post on {topic} for technical readers.",
        backstory=(
            "You explain technical topics with structure and concrete examples. "
            "You keep paragraphs short and link to sources."
        ),
        llm=llm,
        verbose=True,
    )


def editor_agent(llm: LLM) -> Agent:
    return Agent(
        role="Editor",
        goal="Return a publish-ready JSON object with title, tags, and content.",
        backstory=(
            "You return only valid JSON with three fields: title (string), "
            "tags (list of up to 4 short strings), and content (markdown). "
            "No commentary, no code fences."
        ),
        llm=llm,
        verbose=True,
    )


def publisher_agent(llm: LLM, publish_tool: BaseTool) -> Agent:
    return Agent(
        role="Publisher",
        goal="Publish the final blog JSON to Dev.to as a draft.",
        backstory=(
            "You use the publish_to_devto tool exactly once with the JSON "
            "from the editor and return the API response verbatim."
        ),
        llm=llm,
        tools=[publish_tool],
        verbose=True,
    )
