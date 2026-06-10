# `advanced/` — Production version of the demo

This is the same blogging pipeline that `demo/` builds up step by step, wrapped in the things real services need: deterministic source gathering, structured output with retries, caching, idempotent publishing, an HTTP API, auth, rate limiting, and secret hardening.

The content flow is **gather sources → outline → write → edit → (publish)**. Source gathering is deterministic (no LLM); the writer/editor crew runs once over the validated sources.

If you haven't read the demo yet, start there. This folder assumes you understand `Agent` / `Task` / `Crew` / custom tools.

## Module map

| Module                           | What it is                                                                                                | demo equivalent            |
|----------------------------------|-----------------------------------------------------------------------------------------------------------|----------------------------|
| `agents/planner_agent.py`        | Content Strategist agent — drafts the outline before writing                                              | (new)                      |
| `agents/writer_agent.py`         | Writer agent factory                                                                                      | demo Step 04               |
| `agents/editor_agent.py`         | Editor agent factory                                                                                      | demo Step 05               |
| `tasks/outline_task.py`          | Plans title/thesis/sections from the research JSON                                                        | (new)                      |
| `tasks/writing_task.py`          | Rich blog spec + a length/structure/citation **guardrail** with bounded retries                           | demo Step 04               |
| `tasks/editing_task.py`          | Editorial pass; serializes via `output_pydantic=EditedBlog`                                               | demo Step 05               |
| `tools/search_tool.py`           | `SerperSearchClient` — HTTP transport with robust date parsing (ISO / relative / year)                    | demo Step 03               |
| `tools/devto_publisher.py`       | `DevToPublisherClient` — Dev.to HTTP transport used by `PublishingService`                                | demo Step 06               |
| `services/source_service.py`     | Deterministic source gathering: search once, recency-rank, relax freshness floor, undated backfill        | (new)                      |
| `services/crew_service.py`       | Orchestrates the pipeline: gather → run crew once → override sources → finalize references/read-time       | The whole demo, end-to-end |
| `services/cache_service.py`      | Redis-preferred / file-fallback key-value cache                                                           | (new)                      |
| `services/publishing_service.py` | Idempotent publish wrapper around the Dev.to client                                                       | (new)                      |
| `models/*.py`                    | Pydantic models: `BlogDraft` (with word-count floor), `PublishResult`, `PipelineResult`, `ResearchSource` | (new)                      |
| `config/settings.py`             | All runtime config (`.env` via pydantic-settings); secret fields are `SecretStr` + a `reveal()` helper    | (new)                      |
| `runtime.py`                     | `_get_crew_service()` factory + `run_pipeline()` shared by CLI and API                                    | (new)                      |
| `api.py`                         | FastAPI factory; auth + rate-limit middleware; sanitized error responses                                  | (new)                      |
| `cli.py`                         | argparse entrypoint: `generate-only`, `generate-and-publish`, `api`                                       | (new)                      |
| `security.py`                    | `InMemoryRateLimiter` + API-key bucket hashing                                                            | (new)                      |
| `main.py`                        | Thin re-exports of `create_app` and `main`                                                                | (new)                      |
| `utils/markdown.py`              | `extract_json_object`, `estimate_read_minutes`, `WORDS_PER_MINUTE`                                        | demo Step 05               |
| `utils/references.py`            | Render canonical `## References` from sources + validate inline `[n]` citations                            | (new)                      |
| `utils/logger.py`                | `setup_logging` + `get_logger`                                                                            | (new)                      |
| `__init__.py`                    | Opts out of CrewAI/OTEL telemetry before any `crewai` import                                              | (new)                      |

## Recommended reading order

The infrastructure files (cache, security, config, settings) are well-isolated from the AI patterns. Read AI code first, infrastructure off to the side:

1. **`services/source_service.py`** — deterministic, LLM-free source gathering. The strategy: search once, rank dated results newest-first, keep the freshest that clear a freshness floor at `min_year`, relax the floor only when needed (never discarding fresher sources), and use undated results as a last-resort backfill.
2. **`agents/`** — planner, writer, editor. Each file has a docstring linking to its demo equivalent.
3. **`tasks/`** — `outline_task` plans, `writing_task` carries the readability spec + a deterministic guardrail (length band, required sections, inline citations) with bounded retries, `editing_task` does a real edit pass and serializes through `output_pydantic` (a sources-free `EditedBlog`, so the schema has no `HttpUrl`/`format: uri` that OpenAI structured output rejects).
4. **`tools/`** — HTTP transport clients only. `SerperSearchClient` parses ISO/relative/year dates and keeps undated results (with `published_date=None`); `DevToPublisherClient` posts to Dev.to with retries.
5. **`services/crew_service.py`** — the heart of the file:
   - `_run_content_pipeline` — gather sources, run the outline→write→edit crew once (with a graceful fallback that drops strict length enforcement if the writing guardrail can't converge), override `blog.sources` with the validated set, then finalize references and read-time.
   - `_run_publish_pipeline` — publishes **deterministically** via `PublishingService` (idempotent, retried). Publishing is a side effect, not LLM work, so there's no publisher agent in the loop.
6. **`runtime.py`** — boring glue. One factory, one wrapper.
7. **`cli.py` / `api.py`** — entrypoints. The middleware in `api.py` enforces auth + rate limiting (primitives from `security.py`) and sanitizes errors.
8. **`config/settings.py`** — grouped with `# --- section ---` comments. Skim, don't read.

## What `advanced/` adds on top of the demo

| Concern | Where | Why |
|---------|-------|-----|
| Deterministic source gathering | `services/source_service.py` | Search once, recency-rank, relax the freshness floor only when needed, backfill undated last — instead of re-running the crew per year. |
| Plan → write → edit | `tasks/outline_task.py` + `writing_task.py` + `editing_task.py` | An outline plus a rich writing spec produces structured, readable blogs. |
| Content guardrail + retries | `tasks/writing_task.py` | Enforces length band, required sections, and inline citations; feeds failures back to the writer (`guardrail_max_retries`). |
| Structured output | `tasks/editing_task.py` + `models/blog.py` | `output_pydantic=EditedBlog` validates the schema and retries on malformed output; `BlogDraft` extends it with sources and enforces a minimum word count. |
| Canonical references | `utils/references.py` + `crew_service._finalize_references` | References are re-rendered from the authoritative source list; dangling `[n]` citations are flagged. |
| Honest read-time | `crew_service._finalize_read_minutes` | Reports the true computed read time; an out-of-band value is logged, not faked. |
| Resilient generation | `crew_service._generate_blog_resiliently` | If the writing guardrail can't converge, fall back to a best-effort draft instead of crashing the run. |
| Idempotent publish | `services/publishing_service.py` | Deterministic, retried publish; the same blog title + topic never publishes twice. No LLM in the publish path. |
| Cache | `services/cache_service.py` | Avoid re-running the LLM crew for the same `(topic, min_year)` within TTL. |
| HTTP API | `api.py` + `runtime.py` | FastAPI factory, draft-first publish, OpenAPI auto-docs, sanitized errors. |
| Auth + rate limiting | `api.py` + `security.py` | Per-API-key sliding-window rate limit; constant-time key comparison; key hashed before use as a bucket key. |
| Secret hardening | `config/settings.py` + `__init__.py` | API keys are `SecretStr` (masked everywhere, revealed only at HTTP boundaries); telemetry opted out at import. |

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

48 tests covering:
- Agent / task factory contracts, the writing guardrail logic, and the `EditedBlog` schema (no `format: uri`)
- Deterministic source gathering: recency ranking, freshness-floor relaxation, undated backfill, insufficiency, dedup, and date parsing
- `BlogDraft` word-count floor and references finalization (rebuild, strip, dangling-citation detection)
- Cache file backend roundtrip
- Deterministic, idempotent publishing via `PublishingService` (Dev.to called once)
- Pipeline orchestration: gather → run crew once → override sources, plus graceful guardrail fallback and non-guardrail error propagation
- API auth, rate-limit middleware, 422 guardrail mapping, and 500 error sanitization
