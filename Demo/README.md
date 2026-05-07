# Demo — Build an AI Agent From Scratch

A six-step walkthrough that grows a single LLM call into a research → write → edit → publish multi-agent pipeline using CrewAI.

## Run order

| #  | Notebook                            | What it adds                                                   |
|----|-------------------------------------|----------------------------------------------------------------|
| 01 | `01_init.ipynb`                     | Direct `LLM.call` — no agents yet.                             |
| 02 | `02_research_agent.ipynb`           | Wraps the prompt in `Agent + Task + Crew`.                     |
| 03 | `03_research_agent_with_tool.ipynb` | Adds a built-in web search tool (`SerperDevTool`).             |
| 04 | `04_content_writer_agent.ipynb`     | Chains a writer agent after research via `context=`.           |
| 05 | `05_editor_agent.ipynb`             | Adds an editor agent with format / shape / quality guardrails. |
| 06 | `06_publish_agent.ipynb`            | Adds a custom `BaseTool` and publishes a draft to Dev.to.      |

Run them in order — each step builds on the previous and the "What's New" section at the top of every notebook spells out the delta.

## Required environment variables

Create `.env` at the repo root (one level up from `Demo/`):

```bash
OPENROUTER_API_KEY=...     # steps 01-06
SERPER_API_KEY=...         # steps 03-06
DEVTO_API_KEY=...          # step 06 only
```

Steps 01-02 only need `OPENROUTER_API_KEY`. Step 06 publishes a **draft** (`published: False`) — it will not appear on your public Dev.to feed unless you flip that flag.

## Install

```bash
uv sync --extra dev
```

Then open the notebooks with your IDE / `jupyter lab` and execute cells top-to-bottom.

## Cost note

Every step calls GPT-4o via OpenRouter. Step 06 runs the model 4+ times in one pipeline — expect a few cents per run. Each notebook prints token usage where applicable so you can track it.
