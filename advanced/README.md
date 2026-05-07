# `advanced/` — Production version of the demo

This is the same research → write → edit → publish pipeline that `demo/` builds up step by step, wrapped in the things real services need: caching, idempotent publishing, source-freshness retries, an HTTP API, auth, and rate limiting.

If you haven't read the demo yet, start there. This folder assumes you understand `Agent` / `Task` / `Crew` / custom tools.

## Module map

| Module                           | What it is                                                                                                    | demo equivalent            |
|----------------------------------|---------------------------------------------------------------------------------------------------------------|----------------------------|
| `agents/research_agent.py`       | Research agent factory                                                                                        | demo Step 03               |
| `agents/writer_agent.py`         | Writer agent factory                                                                                          | demo Step 04               |
| `agents/editor_agent.py`         | Editor agent factory                                                                                          | demo Step 05               |
| `agents/publisher_agent.py`      | Publisher agent factory                                                                                       | demo Step 06               |
| `tasks/*.py`                     | One file per task; `description / expected_output / context`                                                  | demo Step 03–06            |
| `tools/search_tool.py`           | Serper client + CrewAI search tool                                                                            | demo Step 03               |
| `tools/devto_publisher.py`       | Dev.to client + CrewAI publish tool (wired to `PublishingService` for idempotency)                            | demo Step 06               |
| `services/crew_service.py`       | Orchestrates the full pipeline. Implements year-by-year source accumulation and the multi-agent publish flow. | The whole demo, end-to-end |
| `services/cache_service.py`      | Redis-preferred / file-fallback key-value cache                                                               | (new)                      |
| `services/publishing_service.py` | Idempotent publish wrapper around the Dev.to client                                                           | (new)                      |
| `models/*.py`                    | Pydantic models: `BlogDraft`, `PublishResult`, `PipelineResult`, `ResearchSource`                             | (new)                      |
| `config/settings.py`             | All runtime configuration; reads `.env` via pydantic-settings                                                 | (new)                      |
| `runtime.py`                     | `_get_crew_service()` factory + `run_pipeline()` shared by CLI and API                                        | (new)                      |
| `api.py`                         | FastAPI factory, request/response models                                                                      | (new)                      |
| `cli.py`                         | argparse entrypoint: `generate-only`, `generate-and-publish`, `api`                                           | (new)                      |
| `security.py`                    | `InMemoryRateLimiter` + API-key bucket hashing                                                                | (new)                      |
| `main.py`                        | Thin re-exports of `create_app` and `main` for the pyproject script and uvicorn factory                       | (new)                      |
| `utils/markdown.py`              | `extract_json_object` — same recovery util introduced in demo Step 05                                         | demo Step 05               |
| `utils/logger.py`                | `setup_logging` + `get_logger`                                                                                | (new)                      |

## Recommended reading order

The infrastructure files (cache, security, config, settings) are well-isolated from the AI patterns. Read in this order to keep AI code in front and infrastructure off to the side:

1. **`agents/`** — same shape as demo, plus the publisher agent. Each file has a docstring linking to its demo equivalent.
2. **`tasks/`** — same demo task contracts, with the freshness/JSON guardrails materialized as task description text.
3. **`tools/`** — note the `Client` + `Tool` split: HTTP transport in the client, CrewAI surface in the tool. `DevToPublisherTool` takes a `PublishingService` so idempotency is enforced even when an agent invokes publishing.
4. **`services/crew_service.py`** — the heart of the file. Two methods to understand:
   - `_run_content_pipeline` — adds year-by-year source accumulation around the demo Step 05 crew.
   - `_run_publish_pipeline` — the same multi-agent publish flow as demo Step 06, plus an idempotency-cache fallback for when the agent's text output isn't valid JSON.
5. **`runtime.py`** — boring glue. One factory, one wrapper.
6. **`cli.py` / `api.py`** — entrypoints. The middleware in `api.py` enforces auth + rate limiting (uses primitives from `security.py`).
7. **`config/settings.py`** — settings are grouped with `# --- section ---` comments. Skim, don't read.

## What `advanced/` adds on top of the demo

| Concern | Where | Why |
|---------|-------|-----|
| Source freshness retry | `crew_service._run_content_pipeline` | Web search sometimes returns too few fresh sources; we accumulate down by year rather than fail. |
| Idempotent publish | `services/publishing_service.py` + `DevToPublisherTool` | The same blog title + topic should never publish twice. |
| Cache | `services/cache_service.py` | Avoid re-running the LLM crew for the same `(topic, min_year)` within TTL. |
| Structured I/O | `models/blog.py` | Pydantic schema with `min_length` / `max_length` / `field_validator`s — guardrails as types. |
| HTTP API | `api.py` + `runtime.py` | FastAPI factory, draft-first publish, OpenAPI auto-docs. |
| Auth + rate limiting | `api.py` + `security.py` | Per-API-key sliding-window rate limit; the API key is hashed before being used as a bucket key. |
| Tests | `tests/` | 13 tests covering agent factories, idempotency, year retries, source accumulation, JSON extraction, and the API security middleware. |

## Run it

From the repo root:

```bash
# generate only
uv run python -m advanced.main generate-only --topic "MCP servers for AI agents"

# generate + publish (Dev.to draft)
uv run python -m advanced.main generate-and-publish --topic "RAG evaluation in production"

# HTTP API
uv run python -m advanced.main api --port 8000
```

The API key for the HTTP server is set via `API_AUTH_KEY` in `.env`. POST to `/v1/blogs/generate` with `X-API-Key: <your key>`.

## Tests

```bash
uv run pytest -q
```

13 tests covering:
- Agent / task factory contracts
- Cache file backend roundtrip
- Idempotency (`PublishingService`)
- Multi-agent publish flow with junk-output recovery
- Source-count guardrail
- Year-by-year source accumulation (across 3 fallback years)
- Search-result normalization
- API auth + rate-limit middleware
