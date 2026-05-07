"""Crew assembly using CrewAI's @CrewBase decorator pattern.

This is the canonical "decorator-style" CrewAI layout for an end-to-end
research → write → edit → publish pipeline:

- `@agent` registers an agent factory method.
- `@task`  registers a task  factory method.
- `@crew`  builds the Crew. Inside it, `self.agents` and `self.tasks` are
  auto-populated lists of every `@agent`- and `@task`-decorated method's return
  value, in declaration order — you do not pass them in by hand.

The class itself is decorated with `@CrewBase`, which wires up that
auto-collection magic. If you've seen the imperative `Crew(agents=[...], tasks=[...])`
form (e.g. in `demo/`), this is the same idea expressed declaratively.
"""

import os

from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool

from basic.code_variant.agents import (
    editor_agent,
    publisher_agent,
    research_agent,
    writer_agent,
)
from basic.code_variant.tasks import (
    editing_task,
    publishing_task,
    research_task,
    writing_task,
)
from basic.code_variant.tools import DevToPublishTool


@CrewBase
class BloggingCrew:
    """End-to-end blogging pipeline: research → write → edit → publish."""

    def __init__(self) -> None:
        # One LLM and the two tool instances, shared across agents. Reads
        # OPENROUTER_API_KEY and DEVTO_API_KEY from the environment; `main.py`
        # calls `load_dotenv()` before constructing this class.
        self._llm = LLM(
            model="openai/gpt-4o",
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        self._search_tool = SerperDevTool()
        self._publish_tool = DevToPublishTool()

    @agent
    def researcher(self) -> Agent:
        return research_agent(self._llm, self._search_tool)

    @agent
    def writer(self) -> Agent:
        return writer_agent(self._llm)

    @agent
    def editor(self) -> Agent:
        return editor_agent(self._llm)

    @agent
    def publisher(self) -> Agent:
        return publisher_agent(self._llm, self._publish_tool)

    @task
    def research(self) -> Task:
        return research_task(self.researcher())

    @task
    def writing(self) -> Task:
        return writing_task(self.writer(), research=self.research())

    @task
    def editing(self) -> Task:
        return editing_task(self.editor(), writing=self.writing())

    @task
    def publishing(self) -> Task:
        return publishing_task(self.publisher(), editing=self.editing())

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
