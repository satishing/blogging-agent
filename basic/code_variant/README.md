# `basic/code_variant/` — Python form (everything in code)

Sibling of `basic/yaml_variant/`. Same four-agent pipeline (**research → write → edit → publish**), but agent and task definitions live in Python factory functions instead of YAML.

## Files

| File          | What it shows                                                                                          |
|---------------|--------------------------------------------------------------------------------------------------------|
| `agents.py`   | Four `Agent` factories: research, writer, editor, publisher. `role / goal / backstory / llm / tools`.  |
| `tasks.py`    | Four `Task` factories chained via `context=`. `description / expected_output / agent / context`.       |
| `tools.py`    | Custom `BaseTool` subclass that publishes a blog JSON to Dev.to as a draft.                            |
| `crew.py`     | `@CrewBase` class wiring the factories via `@agent` / `@task` / `@crew`.                               |
| `main.py`     | Entry point: load env, kickoff the crew, print the publish response.                                   |

This folder is fully self-contained — you could copy it out of the repo and it would still run. The identical `tools.py` lives in the sibling `yaml_variant/` so each variant stays independent of the other.


## The pipeline

```
research_agent ──► writer_agent ──► editor_agent ──► publisher_agent
   (Serper)         (markdown)         (JSON)         (publish_to_devto)
```

When you run this variant you'll see four lines like:

## About warnings
```
WARNING:root:File not found: .../basic/code_variant/config/agents.yaml
WARNING:root:Agent config file not found at .../basic/code_variant/config/agents.yaml. Proceeding with empty agent configurations.
WARNING:root:File not found: .../basic/code_variant/config/tasks.yaml
WARNING:root:Task config file not found at .../basic/code_variant/config/tasks.yaml. Proceeding with empty task configurations.
```

These are harmless. CrewAI's `@CrewBase` always looks for `config/agents.yaml` and `config/tasks.yaml` because that's the canonical scaffold — but this variant intentionally doesn't use them. The crew runs to completion regardless.


## Run it

From the repo root:

```bash
uv run python -m basic.code_variant.main
```

Required env vars in `.env`: `OPENROUTER_API_KEY`, `SERPER_API_KEY`, `DEVTO_API_KEY`. The publisher creates a **draft** on Dev.to.


## What this variant deliberately does not include

- No caching, retries, idempotency, FastAPI, or auth (`advanced/` adds those).
- No source-freshness retries (`advanced/` adds year-by-year fallback).
- No JSON schema validation beyond what the editor agent's prompt enforces.
- No tests — the focus is on the smallest readable end-to-end pipeline.
