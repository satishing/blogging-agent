"""YAML-driven variant of the basic blogging crew.

Same end-to-end pipeline as `basic/code_variant/crew.py`, but agent and task
definitions live in `config/agents.yaml` and `config/tasks.yaml` instead of
Python factory functions. Compare the two sibling folders side by side to see
the trade-off:

- `basic/code_variant/crew.py` — agents/tasks defined in `agents.py` and `tasks.py`.
- `basic/yaml_variant/crew.py` — agents/tasks defined in `config/*.yaml`; this file is much shorter.

What stays in Python no matter which form you use:
- `LLM` instances (not serializable).
- Tool instances (also not serializable; YAML only references them).
- The `@crew` method that returns the actual Crew object.
"""

import os

from crewai import LLM, Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import SerperDevTool

from basic.yaml_variant.tools import DevToPublishTool


@CrewBase
class BloggingCrew:
    """End-to-end blogging pipeline (research → write → edit → publish), YAML-driven."""

    # Tell @CrewBase where to find the YAML configs. These paths are relative
    # to the file that imports this class.
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    def __init__(self) -> None:
        self._llm = LLM(
            model="openai/gpt-4o",
            base_url="https://openrouter.ai/api/v1",
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
        self._search_tool = SerperDevTool()
        self._publish_tool = DevToPublishTool()

    # --- Agents ---
    # `config=` reads role / goal / backstory from agents.yaml.
    # llm and tools come from Python because they aren't serializable.

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config["researcher"],
            llm=self._llm,
            tools=[self._search_tool],
            verbose=True,
        )

    @agent
    def writer(self) -> Agent:
        return Agent(
            config=self.agents_config["writer"],
            llm=self._llm,
            verbose=True,
        )

    @agent
    def editor(self) -> Agent:
        return Agent(
            config=self.agents_config["editor"],
            llm=self._llm,
            verbose=True,
        )

    @agent
    def publisher(self) -> Agent:
        return Agent(
            config=self.agents_config["publisher"],
            llm=self._llm,
            tools=[self._publish_tool],
            verbose=True,
        )

    # --- Tasks ---
    # `config=` reads description / expected_output / agent / context from
    # tasks.yaml. @CrewBase resolves the YAML `agent:` and `context:` strings
    # to the corresponding @agent / @task method results.

    @task
    def research(self) -> Task:
        return Task(config=self.tasks_config["research"])

    @task
    def writing(self) -> Task:
        return Task(config=self.tasks_config["writing"])

    @task
    def editing(self) -> Task:
        return Task(config=self.tasks_config["editing"])

    @task
    def publishing(self) -> Task:
        return Task(config=self.tasks_config["publishing"])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
