# `basic/yaml_variant/` — Declarative YAML form

Sibling of `basic/code_variant/`. Same four-agent pipeline (**research → write → edit → publish**), but agent and task definitions live in YAML instead of Python factory functions.

This is the form that `crewai create crew <name>` scaffolds by default, so it's what you'll see in most CrewAI tutorials.

## Files

| File                 | What it shows                                                                                          |
|----------------------|--------------------------------------------------------------------------------------------------------|
| `config/agents.yaml` | Four agents declared in YAML: role, goal, backstory.                                                   |
| `config/tasks.yaml`  | Four tasks declared in YAML: description, expected_output, agent, context.                             |
| `crew.py`            | `@CrewBase` class. Each `@agent`/`@task` method is one line: `Agent(config=...)` / `Task(config=...)`. |
| `tools.py`           | Custom `BaseTool` subclass that publishes a blog JSON to Dev.to as a draft.                            |
| `main.py`            | Entry point: load env, kickoff the crew with a topic, print the publish response.                      |

## The pipeline

```
research_agent ──► writer_agent ──► editor_agent ──► publisher_agent
   (Serper)         (markdown)         (JSON)         (publish_to_devto)
```

All four tasks run sequentially via `Process.sequential`. Each task receives the previous one's output through `context:` (declared in `tasks.yaml`).

## How YAML wires up to code

When you write this in `tasks.yaml`:

```yaml
writing:
  agent: writer
  context:
    - research
```

`@CrewBase` resolves `writer` → the `Agent` returned by your `writer()` method, and `research` → the `Task` returned by your `research()` method. The method names in `crew.py` (`def writer`, `def research`) **must match the YAML keys exactly**.

## What stays in Python no matter the form

| Concept                        | Why                                                                             |
|--------------------------------|---------------------------------------------------------------------------------|
| `LLM` instance                 | Not serializable. The OpenRouter base URL + API key live in code, not YAML.     |
| Tool instances                 | `SerperDevTool()` and `DevToPublishTool()` are objects with state, not strings. |
| The `@crew` method             | Has to return a real `Crew` object that wires `agents` and `tasks` together.    |
| The `@agent` / `@task` methods | Required so `@CrewBase` knows which YAML key resolves to which class method.    |


## What moved to YAML from Python

| Concept                            | `basic/yaml_variant/`                | `basic/code_variant/`                  |
|------------------------------------|--------------------------------------|----------------------------------------|
| Agent role / goal / backstory      | `config/agents.yaml`                 | `agents.py` factory functions          |
| Task description / expected_output | `config/tasks.yaml`                  | `tasks.py` factory functions           |
| Task → agent wiring                | `agent: writer` in YAML              | `agent=self.writer()` in Python        |
| Task → task context                | `context: [research]` in YAML        | `context=[research]` in Python         |

## Run it

From the repo root:

```bash
uv run python -m basic.yaml_variant.main
```

Required env vars in `.env`: `OPENROUTER_API_KEY`, `SERPER_API_KEY`, `DEVTO_API_KEY`. The publisher creates a **draft** on Dev.to (`published: False`) — review and publish manually from the Dev.to dashboard.


## What this variant deliberately does not include

- No caching, retries, idempotency, FastAPI, or auth (`advanced/` adds those).
- No source-freshness retries (`advanced/` adds year-by-year fallback).
- No JSON schema validation beyond what the editor agent's prompt enforces.
- No tests — the focus is on the smallest readable end-to-end pipeline.
