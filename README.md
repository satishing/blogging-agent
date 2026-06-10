# Production Blogging Agent (CrewAI)

Production-grade backend for technical AI blogging:
- Accepts any topic
- Researches latest sources (date-grounded web search)
- Writes and edits a learner-focused blog (target 6-8 minute read)
- Publishes to Dev.to as **draft first**
- Supports both **CLI** and **API** runtime modes

## Learning path

All three folders solve the **same problem** — a four-agent blogging pipeline (research → write → edit → publish to Dev.to). They differ only in the level of structure and production polish:

| Folder      | Format                             | Production concerns                                     | Audience                                                        |
|-------------|------------------------------------|---------------------------------------------------------|-----------------------------------------------------------------|
| `demo/`     | Six Jupyter notebooks              | None — exploratory, builds up step by step              | First-time learners. Each notebook adds one new concept.        |
| `basic/`    | Structured Python with `@CrewBase` | None — clean reference for the decorator pattern        | Python developers who want a single readable end-to-end script. |
| `advanced/` | Structured Python with factories   | Caching, idempotent publishing, FastAPI, retries, tests | Engineers shipping the agent to production.                     |

Suggested order: **`demo/` → `basic/` → `advanced/`**. The notebooks teach the moving parts; `basic/` shows the same end-to-end pipeline as a structured program using CrewAI's decorator scaffold; `advanced/` is what production looks like once you wrap that pipeline in caching, idempotency, an HTTP API, and tests.

Recommended reading order inside `advanced/`: `agents/` → `tasks/` → `tools/` → `services/source_service.py` → `services/crew_service.py` → `main.py`. The rest is infrastructure (settings, cache, security middleware).

## Architecture

```mermaid
flowchart LR
cliClient[CLIClient] --> appMain[advanced/main.py]
apiClient[APIClient] --> appMain
appMain --> crewService[CrewService]
crewService --> sourceService[SourceService]
sourceService --> searchClient[SerperSearchClient]
searchClient --> serperAPI[SerperAPI]
crewService --> writerAgent[WriterAgent]
crewService --> editorAgent[EditorAgent]
crewService --> publisherAgent[PublisherAgent]
publisherAgent --> publishTool[DevToPublisherTool]
publishTool --> publishingService[PublishingService]
publishingService --> devtoClient[DevToPublisherClient]
devtoClient --> devtoAPI[DevToAPI DraftPublish]
crewService --> cacheService[CacheService]
cacheService --> redisOrFile[RedisOrFileCache]
publishingService --> cacheService
```

## Project Structure

```text
blogging-agent/
├── basic/                    # End-to-end pipeline using @CrewBase decorators
│   ├── README.md             # intro to both variants below
│   ├── yaml_variant/         # Agent/task definitions in YAML (CrewAI's default scaffold)
│   │   ├── config/
│   │   │   ├── agents.yaml
│   │   │   └── tasks.yaml
│   │   ├── crew.py           # Agent(config=...) / Task(config=...)
│   │   ├── tools.py          # custom DevToPublishTool
│   │   ├── main.py           # python -m basic.yaml_variant.main
│   │   └── README.md
│   └── code_variant/         # Agent/task definitions in Python factories
│       ├── agents.py
│       ├── tasks.py
│       ├── crew.py
│       ├── tools.py          # identical copy — variants stay independent
│       ├── main.py           # python -m basic.code_variant.main
│       └── README.md         # (no config/ — this variant doesn't use YAML)
├── demo/                     # Notebooks for first-time AI agent learners
│   ├── 01_init.ipynb
│   ├── 02_research_agent.ipynb
│   ├── 03_research_agent_with_tool.ipynb
│   ├── 04_content_writer_agent.ipynb
│   ├── 05_editor_agent.ipynb
│   ├── 06_publish_agent.ipynb
│   └── README.md
├── advanced/                 # Production-shaped version of the same pipeline
│   ├── agents/
│   ├── tasks/
│   ├── tools/
│   ├── services/
│   ├── models/
│   ├── config/
│   ├── utils/
│   └── main.py
├── tests/
├── data/
│   ├── cache/
│   ├── outputs/
│   └── logs/
├── pyproject.toml
└── README.md
```

## Environment Variables

Create `.env` in repo root:

```bash
cp .env.example .env
```

Then edit values:

```bash
OPENROUTER_API_KEY=your_openrouter_key
SERPER_API_KEY=your_serper_key
DEVTO_API_KEY=your_devto_key  # required only for publish=true
API_AUTH_KEY=replace_with_a_long_random_key

# Optional
MODEL_NAME=openai/gpt-4o
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
CACHE_BACKEND=file     # file or redis
REDIS_URL=redis://localhost:6379/0
PUBLISH_AS_DRAFT=true  # default is draft-first in code
LOG_LEVEL=INFO
API_AUTH_ENABLED=true
API_AUTH_HEADER_NAME=X-API-Key
API_RATE_LIMIT_ENABLED=true
API_RATE_LIMIT_PER_MINUTE=30
API_RATE_LIMIT_WINDOW_SECONDS=60
SOURCE_YEAR_RETRY_STEPS=3   # how far below the target year the freshness floor may relax
SEARCH_QUERY_VARIANTS=1     # 1=topic only; 2 adds "<topic> latest"; 3 adds "<topic> <year>"
```

## Setup (Local)

### 1) Install dependencies (uv only)

```bash
uv sync --extra dev
```

### 2) Install pre-commit hooks

```bash
uv run pre-commit install
```

Optional one-time run across repository:

```bash
uv run pre-commit run --all-files
```

### 3) Run tests

```bash
uv run pytest
```

Important:
- Use `uv run ...` for all commands.
- Do not run bare `pytest` / `python` directly from global environment.

## Local Run Instructions

### CLI mode

Generate + publish (draft-first):

```bash
uv run python -m advanced.main generate-and-publish --topic "MCP servers for AI agents" --min-year 2026
```

Generate only (no publish):

```bash
uv run python -m advanced.main generate-only --topic "RAG evaluation in production" --min-year 2026
```

### API mode

Start API server:

```bash
uv run python -m advanced.main api --host 0.0.0.0 --port 8000
```

Generate endpoint:

```bash
curl -X POST http://localhost:8000/v1/blogs/generate \
  -H "X-API-Key: replace_with_a_long_random_key" \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Agentic observability patterns",
    "publish": false,
    "force_refresh": false,
    "min_year": 2026
  }'
```

## Redis Setup (Optional but Recommended)

### Docker

```bash
docker run --name blogging-agent-redis -p 6379:6379 -d redis:7
```

Then set:

```bash
CACHE_BACKEND=redis
REDIS_URL=redis://localhost:6379/0
```

### macOS (Homebrew)

```bash
brew install redis
brew services start redis
```

## Guardrails and Reliability

- Date freshness: sources are expected from `min_year` onward (default 2026).
- If sources from `min_year` are insufficient, pipeline accumulates sources year-by-year from `min_year`, then `min_year - 1`, `min_year - 2`, and `min_year - 3` until `min_sources` is met.
- Structured output: editor task must return strict JSON.
- Readability: blog target is 6-8 minute read.
- Publishing policy: Dev.to draft-first by default.
- Resilience: retries/timeouts in external API tools.
- Cache fallback: Redis preferred, file cache fallback automatically.
- Idempotency: duplicate publish protection via idempotency key.
- API security: API key middleware with configurable header.
- API throttling: in-memory per-key request rate limiting (429 on exceed).

## Mode-Specific Required Variables

- Generate only (`publish=false`):
  - `OPENROUTER_API_KEY`
  - `SERPER_API_KEY`
  - `API_AUTH_KEY` (API mode only)
- Generate and publish (`publish=true`):
  - all above +
  - `DEVTO_API_KEY`

## Troubleshooting

- `Missing OPENROUTER_API_KEY` / `SERPER_API_KEY`: check `.env`.
- `Missing DEVTO_API_KEY`: only required when publishing (`publish=true`).
- `RuntimeError: API auth is enabled but API_AUTH_KEY is missing`: set `API_AUTH_KEY` or disable auth explicitly.
- `ModuleNotFoundError` during tests: run `uv sync --extra dev` and then `uv run pytest`.
- Serper failures: verify API key and outbound network.
- Dev.to publish failures: check `DEVTO_API_KEY` scope and API status.
- Redis unavailable: service automatically falls back to file cache.
- Validation errors on editor JSON: rerun with `--force-refresh` and inspect logs in `data/logs/`.
