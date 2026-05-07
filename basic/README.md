# `basic/` — End-to-end blogging agent in two forms

A working four-agent CrewAI pipeline (**research → write → edit → publish**) targeted at Python developers learning how to build AI agents. Same end-to-end problem as `demo/` and `advanced/`, but presented as a structured Python program using the **`@CrewBase` decorator pattern** — in two interchangeable forms so you can see both styles side by side.

## Two siblings, same crew

```
basic/
├── README.md            ← you are here
├── yaml_variant/        ← declarative form (CrewAI's default scaffold)
│   ├── config/
│   │   ├── agents.yaml  ← role / goal / backstory in YAML
│   │   └── tasks.yaml   ← description / expected_output / agent / context in YAML
│   ├── crew.py          ← @CrewBase using Agent(config=...) / Task(config=...)
│   ├── tools.py         ← custom DevToPublishTool
│   ├── main.py          ← runs as: python -m basic.yaml_variant.main
│   └── README.md
└── code_variant/        ← imperative form (everything in Python)
    ├── agents.py        ← agent factory functions
    ├── tasks.py         ← task factory functions
    ├── crew.py          ← @CrewBase using Python factories
    ├── tools.py         ← custom DevToPublishTool (identical copy)
    ├── main.py          ← runs as: python -m basic.code_variant.main
    └── README.md
```

`code_variant/` has no `config/` directory because it doesn't use YAML — agent/task definitions live in `agents.py` / `tasks.py`. CrewAI logs a four-line "config file not found" warning at startup; it's harmless (see `code_variant/README.md`).

Both variants are **fully self-contained** — each folder could be copied out of the repo and run independently. They produce the same agents, the same tasks, and the same Dev.to draft. They differ only in **where the agent/task definitions live** — YAML or Python.

| Variant         | What's in YAML                                                          | What's in Python                    |
|-----------------|-------------------------------------------------------------------------|-------------------------------------|
| `yaml_variant/` | role, goal, backstory, description, expected_output, agent/context refs | LLM, tool instances, `@crew` method |
| `code_variant/` | nothing                                                                 | everything                          |

The custom `DevToPublishTool` is identical in both folders; we duplicate it so the two variants stay independent of each other rather than one importing from the other.

## Which one should I read first?

| If you want…                                                       | Start with                     |
|--------------------------------------------------------------------|--------------------------------|
| The CrewAI scaffold the official docs and `crewai create crew` use | `yaml_variant/`                |
| Everything visible in code with IDE refactor support               | `code_variant/`                |
| To compare the two styles                                          | Read both READMEs side by side |

## Run them

From the repo root:

```bash
# YAML form
uv run python -m basic.yaml_variant.main

# Python form
uv run python -m basic.code_variant.main
```

Both need the same env vars in `.env`: `OPENROUTER_API_KEY`, `SERPER_API_KEY`, `DEVTO_API_KEY`. Both publish to Dev.to as a **draft** (`published: False`).

## When to pick which form

| Use Python (`code_variant/`)                                  | Use YAML (`yaml_variant/`)                                                      |
|---------------------------------------------------------------|---------------------------------------------------------------------------------|
| You want IDE refactor support and type checking on prompts    | You want non-engineers to edit prompts without touching code                    |
| You need conditional logic or runtime-computed prompt strings | Prompts are static text                                                         |
| You're learning CrewAI and want everything visible in code    | You're A/B testing prompts and want git diffs that show only the wording change |
| Small crew, single file is fine                               | Many agents/tasks; YAML keeps things flat and scannable                         |

Functionally the two forms are equivalent. Pick whichever your team will be happier maintaining six months from now.

## How `basic/` relates to the rest of the repo

All three folders solve the **same problem**. They differ only in how much structure and production polish surrounds the same four-agent pipeline:

| Folder      | Format                                 | Production concerns                                     | When to read it                                                     |
|-------------|----------------------------------------|---------------------------------------------------------|---------------------------------------------------------------------|
| `demo/`     | Six Jupyter notebooks                  | None — exploratory, builds up step by step              | First — see how each piece is added one step at a time.             |
| `basic/`    | Structured Python with `@CrewBase`     | None — clean reference for the decorator pattern        | Second — same end-to-end pipeline as a runnable structured program. |
| `advanced/` | Structured Python with factory pattern | Caching, idempotent publishing, FastAPI, retries, tests | Third — what production looks like.                                 |

## What `basic/` deliberately does not include

- No caching, retries, idempotency, FastAPI, or auth (`advanced/` adds all of those).
- No source-freshness retries (`advanced/` adds year-by-year fallback).
- No JSON schema validation beyond what the editor agent's prompt enforces.
- No tests — the focus is on the smallest readable end-to-end pipeline.
