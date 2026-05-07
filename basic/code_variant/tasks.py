"""Task definitions: description, expected_output, agent, context.

Four tasks chained via `context=`, run in declaration order by `Process.sequential`:

1. `research_task`   — agent uses its search tool to gather sources.
2. `writing_task`    — reads research output, writes a Markdown blog.
3. `editing_task`    — reads the Markdown, returns publish-ready JSON.
4. `publishing_task` — feeds the JSON to the publish_to_devto tool.

The `{topic}` placeholder in `description` is filled in by `kickoff(inputs=...)`
in `main.py`.
"""

from crewai import Agent, Task


def research_task(agent: Agent) -> Task:
    return Task(
        description=(
            "Research {topic}. Use the search tool. "
            "Collect the most recent, credible sources and pull out the key points."
        ),
        expected_output=(
            "A short bullet-point summary with each point followed by its source URL."
        ),
        agent=agent,
    )


def writing_task(agent: Agent, research: Task) -> Task:
    return Task(
        description=(
            "Write a blog post about {topic} for technical readers, "
            "using only the information in the research notes. "
            "Keep paragraphs short. Include source links inline."
        ),
        expected_output="A clear, well-structured Markdown blog post.",
        agent=agent,
        context=[research],
    )


def editing_task(agent: Agent, writing: Task) -> Task:
    return Task(
        description=(
            "Convert the Markdown blog post into a single JSON object with keys: "
            "title (string), tags (list of up to 4 short strings), content (markdown). "
            "Return only the JSON, no commentary, no code fences."
        ),
        expected_output='{"title": "...", "tags": ["ai"], "content": "..."}',
        agent=agent,
        context=[writing],
    )


def publishing_task(agent: Agent, editing: Task) -> Task:
    return Task(
        description=(
            "Use the publish_to_devto tool exactly once with the JSON object "
            "produced by the editor. Return the tool's response verbatim."
        ),
        expected_output="The exact JSON response from the Dev.to publish API.",
        agent=agent,
        context=[editing],
    )
