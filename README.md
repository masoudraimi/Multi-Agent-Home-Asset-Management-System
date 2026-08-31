# WiseWombat — Multi-Agent Home Asset Management

[![Python](https://img.shields.io/badge/python-%3E%3D3.13-3776AB?logo=python&logoColor=white)](https://python.org)
[![uv](https://img.shields.io/badge/uv-package%20manager-DE5FE9)](https://docs.astral.sh/uv)
[![Reflex](https://img.shields.io/badge/Reflex-%3E%3D0.9-5646ED?logo=reflex&logoColor=white)](https://reflex.dev)
[![LangGraph](https://img.shields.io/badge/LangGraph-%3E%3D1.2-1C3C3C)](https://langchain-ai.github.io/langgraph/)
[![LangChain](https://img.shields.io/badge/LangChain-1.5-1C3C3C)](https://python.langchain.com)
[![Deep Agents](https://img.shields.io/badge/Deep%20Agents-research%20sub%E2%80%91agent-1C3C3C)](https://docs.langchain.com/oss/python/deepagents/overview)
[![PydanticAI](https://img.shields.io/badge/PydanticAI-structured%20output-E92063?logo=pydantic&logoColor=white)](https://ai.pydantic.dev)
[![LlamaIndex](https://img.shields.io/badge/LlamaIndex-chunking-6A5ACD)](https://developers.llamaindex.ai)
[![Claude](https://img.shields.io/badge/Claude-Sonnet%204.6%20%2F%20Haiku%204.5-D97757)](https://anthropic.com)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-compatible-74AA9C)](https://openrouter.ai)
[![LangSmith](https://img.shields.io/badge/LangSmith-tracing-1C3C3C)](https://smith.langchain.com)
[![Langfuse](https://img.shields.io/badge/Langfuse-self%E2%80%91hostable-1B7BF7)](https://langfuse.com)
[![Neon](https://img.shields.io/badge/Neon-Postgres%20%2B%20pgvector-00E699?logo=neon&logoColor=black)](https://neon.tech)
[![Supabase](https://img.shields.io/badge/Supabase-Postgres%20%2B%20pgvector-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com)
[![pytest](https://img.shields.io/badge/pytest-%3E%3D9-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org)
[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](.github/workflows/ci.yml)

A conversational AI agent for tracking home assets, maintenance, and spend. Ask plain-language questions about your appliances, HVAC, plumbing, vehicles, plants and trees — the agent chooses the right specialist, calls the right tools, and pauses for human approval before destructive actions.

Built as a working household tool **and** a portfolio piece for modern agent architecture: **LangGraph state machines** with a layered security/governance node sequence (rate limiting, two-layer prompt-injection defense, pgvector-backed RAG auto-retrieval, tamper-evident audit logging), **human-in-the-loop via `interrupt()`**, **provider-agnostic LLM factory** (Anthropic / OpenRouter / Claude Code CLI with OAuth), contained real usage of **Deep Agents** and **PydanticAI** alongside LangGraph (see [ADR 0001](docs/architecture-decisions/0001-orchestration-framework-choice.md) for why), an **LLM-as-judge eval harness** with CI, and **first-class observability** (LangSmith / Langfuse / Prometheus / structured, hash-chained audit).

## Demo

```text
You:   Add my dishwasher.
Agent: [tool: get_onboarding_questions]
       Let's get your dishwasher set up. What brand and model is it?

You:   Bosch Series 6, March 2023, $1,200.
Agent: [tool: review_asset_draft] → confidence: high, ready_to_save: true
       Here's the summary — confirm?
         Name: Dishwasher · Brand: Bosch · Model: Series 6
         Purchased: 2023-03-01 · Price: $1,200

You:   Yes.
Agent: [tool: add_asset]  Saved. Your HVAC filter is 12 days overdue.

You:   Delete the old lemon tree, id 4.
Agent: [tool: review_delete_asset]
       ⚠  I've prepared the deletion. Please confirm in the approval card.
       [Reflex UI shows Approval Card → user clicks Confirm]
       [graph resumes via Command(resume={"approved": True})]
       [tool: delete_asset]  Deleted "Lemon Tree" (id=4). 3 maintenance records
       cascaded.
```

## Architecture

```text
                            ┌──────────────────────┐
                            │  Reflex UI (3000)    │  chat + assets + schedule
                            │  send_message()      │  + admin
                            └──────────┬───────────┘
                                       │
                                       ▼
                       ┌────────────────────────────┐
                       │  agent/runner.py           │  routes on LLM_PROVIDER
                       └───┬────────────────────┬───┘
                           │                    │
             ┌─────────────┘                    └──────────────┐
    (claude_cli path)                              (claude_sdk / openrouter)
             │                                                 │
             ▼                                                 ▼
   ┌───────────────────┐                       ┌────────────────────────────┐
   │ agent/cli_runner  │                       │ dispatch_turn              │  @traceable
   │   subprocess:     │                       │   ├─ classify_intent (Haiku)
   │   claude --print  │                       │   └─ _run_specialist_events
   │   --mcp-config    │                       │        │ (parallel fan-out
   │   --stream-json   │                       │        │  on compound queries)
   │                   │                       │        ▼
   │ + OAuth (no key)  │                       │  ┌───────────────────────────┐
   │ + EventBus for    │                       │  │  LangGraph specialist     │
   │   approvals       │                       │  │  ──────────────────────   │
   │ + __approval_     │                       │  │  enter (rate-limit gate)  │
   │   confirmed__     │                       │  │   → guardrail_in (inject. │
   │   sentinel        │                       │  │     scan, regex+LLM)      │
   └───────────────────┘                       │  │   → retrieve (auto-RAG,   │
                                               │  │     pgvector + citations) │
                                               │  │   → llm ↔ tools ──┐       │
                                               │  │   → guardrail_tool│       │
                                               │  │     _output       │       │
                                               │  │       [handle_    ┘       │  asset only
                                               │  │       approval]           │  interrupt()
                                               │  │   → guardrail_out (PII)   │
                                               │  │   → exit (audit + metrics)│
                                               │  └───────────────────────────┘
                                               └────────────────────────────┘
                                                            │
                                     ┌──────────────────────┼──────────────────────┐
                                     ▼                      ▼                      ▼
                              ┌────────────┐         ┌────────────┐         ┌────────────┐
                              │  asset     │         │ maintenance│         │  insights  │
                              │  graph.py  │         │  graph.py  │         │  graph.py  │
                              └─────┬──────┘         └─────┬──────┘         └─────┬──────┘
                                    │                      │                      │
                                    └──────────────────────┼──────────────────────┘
                                                           ▼
                                            ┌────────────────────────┐
                                            │  tools/langchain_tools │  17 shared @tool wrappers
                                            │      (uses tools/db.py │  (14 CRUD + 3 memory) +
                                            │      + tools/schemas)  │  2 insights-only tools
                                            └───────────┬────────────┘  (deep_research_analysis,
                                                                        generate_shareable_report)
                                                        ▼
                                     ┌───────────────────────────────────────┐
                                     │  db/ provider — Supabase | Neon       │  user-scoped
                                     └───────────────────────────────────────┘
```

### Core primitives

| Concern | Module | Notes |
|---|---|---|
| Structured logs | [core/logging.py](core/logging.py) | structlog JSON in prod, colour console in dev; contextvar-based correlation IDs; PII redaction |
| Metrics | [core/metrics.py](core/metrics.py) | Prometheus counters/histograms + in-memory ring buffer for the admin UI |
| Audit trail | [core/audit.py](core/audit.py) | Pydantic-validated JSONL, **tamper-evident hash chain** (each entry embeds the previous entry's hash; `verify_chain()` / `scripts/verify_audit_log.py` detect the first broken link), weekly gzip rotation with chain continuity preserved across rotation |
| Alerts | [core/alerts.py](core/alerts.py) | Discord/Slack webhooks with severity filtering |
| Guardrails | [core/guardrails.py](core/guardrails.py) | Two-layer prompt-injection defense (regex short-circuit + [core/injection_classifier.py](core/injection_classifier.py) LLM classifier for paraphrased/encoded attempts) covering the user message, tool output, and retrieved RAG context; PII redaction (SSN/CC/passport/email/phone/IBAN/address) + output truncation |
| Rate limiting | [core/rate_limit.py](core/rate_limit.py) | Per-`(user, agent)` in-process token bucket, sized from `agent.yaml:rate_limit_per_min`/`rate_limit_burst` |
| Tool authorization | [core/authz.py](core/authz.py) | `require_role()` decorator gating individual `@tool` calls by the caller's role (never an LLM-visible argument — same ContextVar pattern as `user_id`) |
| Sessions | [core/session.py](core/session.py) | `contextvars.ContextVar` for per-request user + role scoping (async + subprocess) |
| Checkpointer | [core/checkpointer.py](core/checkpointer.py) | In-memory / SQLite / Postgres factory (LangGraph state persistence) |
| LLM factory | [core/llm.py](core/llm.py) | Provider selection; explicit `MissingCredentialsError` on misconfig |
| Pricing | [core/pricing.py](core/pricing.py) | Per-model USD rate table for the budget guard |
| Memory | [core/memory/](core/memory/) | short-term (token-budget-aware context trimming), long-term (per-user KV), semantic (pgvector-backed RAG — see [RAG architecture](#rag-architecture)) |

### Specialist graphs share one builder

All three specialists are compiled by [`SpecialistGraph`](agents/_specialist.py) with the same shape:

```
START → enter → guardrail_in → retrieve → llm ⇄ tools → guardrail_tool_output → guardrail_out → exit → END
  │         │                                                    │
  │         └─► exit (injection blocked)                         └─► handle_approval (asset only, interrupt())
  └─► exit (rate limited)
```

- **`enter`** — binds correlation IDs, checks the per-`(user, agent)` rate limit ([core/rate_limit.py](core/rate_limit.py)); throttled turns short-circuit straight to `exit` with zero LLM cost.
- **`guardrail_in`** — layered injection scan (regex, then an LLM classifier if the regex is clean) on the user's message; a block short-circuits to `exit`.
- **`retrieve`** — no-op unless `agent.yaml:retrieve_semantic` is true; otherwise queries pgvector-backed semantic memory for the user's message and injects cited hits into the system prompt. Hits are themselves injection-scanned before being stored, since this runs *before* the first `llm` call — scanning downstream would be too late. See [RAG architecture](#rag-architecture).
- **`guardrail_tool_output`** — scans tool results that could carry user-crafted free text (asset notes, search results) for indirect injection, neutralizing a hit rather than failing the whole turn.
- **`guardrail_out`** — PII redaction + output length cap on the final answer.

Loop-engineering rules applied to every node:

- **Retries**: tenacity, 3 attempts, exp-backoff 1–8s. Config errors (`MissingCredentialsError`) + upstream 401/403/429 skip retry to fail fast with an actionable message.
- **Max iterations**: enforced from `agent.yaml:max_turns` (asset=25, maintenance=20, insights=15, orchestrator=5).
- **Budget**: per-turn `budget_usd` cap from `agent.yaml`. `core/pricing.py` accumulates cost from `usage_metadata`; over-budget terminates with `outcome:budget`.
- **Rate limit**: per-`(user, agent)` token bucket from `agent.yaml:rate_limit_per_min`/`rate_limit_burst` (defaults 30/min, burst 10); throttled turns terminate with `outcome:rate_limited`.
- **Timeouts**: 30s LLM / 10s tool via `RunnableLambda.with_config`.
- **Termination reason**: always set at exit (`ok` | `budget` | `max_iter` | `guardrail` | `rate_limited` | `error`), emitted in metrics.

### Human-in-the-loop

Destructive `delete_asset` runs through a two-step gate:

1. LLM calls `review_delete_asset(id)` → tool returns payload with asset details and cascade count.
2. Router detects `approval_requested`, sends state to `handle_approval` node.
3. `handle_approval` calls LangGraph `interrupt(payload)` — graph **pauses**, state persists in checkpointer.
4. Reflex renders an Approval Card; the adapter surfaces a `pending_approval` UI event with `thread_id`.
5. User clicks **Confirm** → Reflex calls `resume_graph_turn(thread_id, approved=True)` → LangGraph resumes `handle_approval`.
6. `handle_approval` executes `db.delete_asset` **directly** (no extra LLM tokens), writes three audit events, produces the confirmation message.

## RAG architecture

Semantic memory ([core/memory/semantic.py](core/memory/semantic.py)) is pgvector-backed, not a Python-side cosine loop:

- **Storage**: `semantic_memory.embedding_vec vector(1024)` on both `db/neon.py` and `db/supabase.py`, with an HNSW cosine index (`vector_cosine_ops`). Similarity search runs in SQL (`ORDER BY embedding_vec <=> query LIMIT k` on Neon; a `match_semantic_memory` SQL function called via `.rpc()` on Supabase, since PostgREST can't express that ordering directly).
- **Embeddings**: [Voyage AI](https://voyageai.com) `voyage-3.5-lite` (1024-dim) is the expected default. If `VOYAGE_API_KEY` is missing or invalid, retrieval falls back to a deterministic 512-dim hash stub — but loudly: a stderr banner and a structured `semantic_embedding_stub_fallback_active` log fire once per process, and every row is tagged with its `embedding_model` (`voyage-3.5-lite` vs `hash_stub_v1`) so degraded rows are identifiable later. A stub-dimensioned query embedding can't be compared against the `vector(1024)` column at all, so `retrieve()` returns `[]` rather than a meaningless search.
- **Chunking**: [knowledge/rag/chunker.py](knowledge/rag/chunker.py) uses LlamaIndex's `SentenceSplitter` (imported standalone — no full LlamaIndex application) for sentence-aware boundaries on long-form text. Structured short records (plant care, checklist items) skip chunking entirely — they're already atomic.
- **Ingestion**: [knowledge/rag/ingest.py](knowledge/rag/ingest.py)`::ingest_document()` chunks + stores with citation metadata (`source`, `source_type`, `chunk_index`). [knowledge/rag/indexer.py](knowledge/rag/indexer.py)`::index_all()` bootstraps plant care + checklist records plus a bundled sample long-form doc ([knowledge/rag/sample_docs/dishwasher_manual_excerpt.md](knowledge/rag/sample_docs/dishwasher_manual_excerpt.md)) on first run.
- **Auto-retrieval**: every specialist with `agent.yaml:retrieve_semantic: true` (all three, as of this revision) runs the `retrieve` graph node automatically before the first `llm` call each turn — no explicit tool call needed. Hits are injected into the system prompt with bracketed citation tags (`[checklist#12]`), and the LLM is instructed to cite them. The `recall_knowledge` tool remains available for a refined follow-up query mid-turn.
- **Migration**: [scripts/migrate_pgvector.py](scripts/migrate_pgvector.py) clears and re-indexes semantic memory with real embeddings — the correct path here since all current content is reproducible from `core/schema.py`, and pre-pgvector rows are typically stub-embedded anyway.

## AI security

- **Prompt injection — two layers**: a fast regex pass ([core/guardrails.py](core/guardrails.py)) catches known patterns (including zero-width-space evasion); anything that gets through escalates to an LLM classifier ([core/injection_classifier.py](core/injection_classifier.py), cheap Haiku-tier call, never raises) tuned per content source (`user_message` / `tool_output` / `retrieved_context`). Coverage extends past the raw user message: `guardrail_tool_output` scans tool results for indirect injection (e.g. a crafted asset note), and `retrieve` scans retrieved RAG content *before* it ever reaches a prompt.
- **PII / data leakage**: regex redaction covers SSN, credit card, passport, email, phone, IBAN, and street-address patterns, enabled uniformly across all four agents (previously inconsistent — off for two of four). Per-user data isolation is enforced via a `contextvars.ContextVar` `user_id` (`core/session.py`) that's never an LLM tool argument, so it can't be spoofed by prompt content — every `tools/db.py` query is scoped by it.
- **Audit — tamper-evident**: `core/audit.py` hash-chains every entry (`entry_hash = sha256(prev_hash + canonical_json(entry))`); `verify_chain()` / `scripts/verify_audit_log.py` detect the first broken link from an edited or deleted line, and chain continuity survives log rotation via a sidecar state file.
- **Rate limiting**: an in-process token bucket per `(user, agent)` ([core/rate_limit.py](core/rate_limit.py)), sized from `agent.yaml`. Documented as process-local by design — a multi-instance deployment would need a shared store instead.
- **Tool-level authorization**: `core/authz.py`'s `require_role()` decorator gates `delete_asset` by role (in addition to the HITL approval above), reading the role from the same non-spoofable ContextVar pattern as `user_id`. Today ownership is the real access boundary for asset mutations, not role — the decorator proves the enforcement + audit path end-to-end and is the seam for an actually role-restricted tool later.
- **Governance**: per-agent `budget_usd`/`max_turns` caps, model tier fixed per agent config, `.gitleaks`-scanned secrets in CI.

## Orchestration framework breadth

LangGraph/LangChain is the primary orchestrator (see above), chosen because this app's requirements — durable checkpointed state, an explicit graph for governance nodes, native `interrupt()`-based HITL — are exactly what it's built for. Two other frameworks named alongside it in the "orchestration frameworks" space earned a real, contained role instead of a wholesale swap:

- **[Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview)** ([agents/insights/deep_research.py](agents/insights/deep_research.py)) — a `create_deep_agent`-built sub-agent for genuinely open-ended, multi-step analysis questions ("why is my utility bill high"), exposed to the insights specialist as the `deep_research_analysis` tool. A compatibility spike confirmed its compiled graph accepts this app's existing `@tool`s and `BaseChatModel`s directly, and its state schema is extensible — but its own graph topology has none of `SpecialistGraph`'s governance nodes, so it runs *behind* that perimeter as a tool call rather than replacing the graph.
- **[PydanticAI](https://ai.pydantic.dev)** ([agents/insights/report_agent.py](agents/insights/report_agent.py)) — a small, contained structured-extraction step (`generate_shareable_report` tool) that turns free-text analysis notes into a validated `HomeInsightsReport`, using the framework purpose-built for typed, validated agent output.
- **[LlamaIndex](https://developers.llamaindex.ai)** — its `SentenceSplitter` handles chunk boundaries in the RAG ingestion pipeline (see [RAG architecture](#rag-architecture)) rather than a hand-rolled splitter.
- **Semantic Kernel** was evaluated and not adopted — see [docs/architecture-decisions/0001-orchestration-framework-choice.md](docs/architecture-decisions/0001-orchestration-framework-choice.md) for the full reasoning (its Python SDK is the secondary surface behind a .NET-first implementation, and nothing about this app's requirements points at its actual strengths).

## Tech stack

**Runtime**

- [Reflex ≥ 0.9](https://reflex.dev) — Python full-stack (React frontend + FastAPI backend). Vite dev server on 3000, WebSocket backend on 8001.
- [LangGraph ≥ 1.2](https://langchain-ai.github.io/langgraph/) — state-graph orchestration, native `interrupt()` HITL, checkpointers.
- [LangChain Core 1.5](https://python.langchain.com) — `@tool` decorators + ChatModel abstraction bound to the specialists.
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) + [langchain-anthropic](https://pypi.org/project/langchain-anthropic/) — `ChatAnthropic`.
- [OpenAI SDK](https://github.com/openai/openai-python) + [langchain-openai](https://pypi.org/project/langchain-openai/) — `ChatOpenAI` pointed at OpenRouter for cross-provider models.
- [Claude Code CLI](https://docs.claude.com/en/docs/claude-code) — subprocess mode, OAuth-based auth for the `claude_cli` provider path.
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — stdio server exposing tools to the CLI subprocess.

**Orchestration frameworks beyond LangGraph** — see [Orchestration framework breadth](#orchestration-framework-breadth) for why each was chosen and how it's scoped:

- [Deep Agents](https://docs.langchain.com/oss/python/deepagents/overview) — multi-step planning sub-agent for open-ended insights analysis.
- [PydanticAI](https://ai.pydantic.dev) — validated structured-output extraction for shareable reports.
- [LlamaIndex Core](https://developers.llamaindex.ai) — `SentenceSplitter` for RAG chunk boundaries (imported standalone, no full LlamaIndex app).

**Data layer**

- [Neon](https://neon.tech) or [Supabase](https://supabase.com) Postgres with the [pgvector](https://github.com/pgvector/pgvector) extension (interchangeable — pick with `DB_PROVIDER`). HNSW cosine index on `semantic_memory.embedding_vec`.
- [psycopg 3](https://www.psycopg.org/psycopg3/) + [pgvector-python](https://github.com/pgvector/pgvector-python) (Neon path), [supabase-py](https://github.com/supabase/supabase-py) + a `match_semantic_memory` SQL function called via `.rpc()` (Supabase path, since PostgREST can't express `ORDER BY ... <=>` directly).
- [Pydantic v2](https://docs.pydantic.dev) — schemas for every tool input and every domain category (see `schema/`).

**Observability**

- [structlog 26](https://www.structlog.org) — JSON logs with contextvar-based correlation IDs (`request_id`, `thread_id`, `user_id`, `trace_id`, `agent`).
- [prometheus_client](https://github.com/prometheus/client_python) — turn/tool/guardrail/budget/rate-limit/checkpoint metrics.
- [LangSmith](https://smith.langchain.com) *or* self-hosted [Langfuse](https://langfuse.com) — per-turn root span with parallel branches per specialist.
- [tenacity](https://tenacity.readthedocs.io) — exponential-backoff retries with config-error exclusions.

**Auth / infrastructure**

- [bcrypt](https://pypi.org/project/bcrypt/) — password hashing for admin users.
- [python-dotenv](https://github.com/theskumar/python-dotenv) — env loading.
- [Docker](https://docker.com) + [uv](https://docs.astral.sh/uv) — deployment.
- [GitHub Actions](https://github.com/features/actions) + [gitleaks](https://github.com/gitleaks/gitleaks) — CI (offline tests + secrets scan + prompt-version check on every PR; real-API eval on a separate nightly/manual workflow). See [Continuous integration](#continuous-integration).

**Optional**

- [Voyage AI](https://voyageai.com) `voyage-3.5-lite` — semantic embeddings (falls back to a deterministic hash stub, loudly logged, if `VOYAGE_API_KEY` isn't set — see [RAG architecture](#rag-architecture)).

## Repository layout

```
home-asset-agent/
├── agent/                       Runtime router
│   ├── runner.py                run_turn (sync) / run_turn_in_loop (async); routes by LLM_PROVIDER
│   ├── cli_runner.py            Claude Code CLI subprocess dispatch (OAuth path)
│   └── langgraph_adapter.py     graph events → UI event dicts + interrupt/resume + error classifier
├── agents/                      Multi-agent architecture
│   ├── state.py                 Shared AgentState TypedDict
│   ├── _specialist.py           SpecialistGraph builder — enter/guardrail_in/retrieve/llm/tools/
│   │                            guardrail_tool_output/guardrail_out/exit, used by all 3
│   ├── asset/       ← inventory, onboarding, delete-with-approval
│   ├── maintenance/ ← scheduling, plant care, Telegram digest
│   ├── insights/    ← spend analytics, warranty alerts
│   │   ├── deep_research.py     Deep Agents research sub-agent (deep_research_analysis tool)
│   │   └── report_agent.py      PydanticAI structured report tool (generate_shareable_report)
│   └── orchestrator/
│       ├── dispatcher.py        Functional dispatch (classify → parallel fan-out → merge, @traceable)
│       ├── agent.py             Thin _run_specialist_events helper
│       └── workflows/routing.py Haiku-backed intent classifier
├── core/                        Cross-cutting primitives (see table above)
│   ├── guardrails.py            Layered injection defense (regex + classifier) + PII redaction
│   ├── injection_classifier.py  LLM-based injection classifier (2nd defense layer)
│   ├── rate_limit.py            Per-(user, agent) token-bucket rate limiter
│   ├── authz.py                 require_role() tool-level authorization decorator
│   └── audit.py                 Tamper-evident hash-chained audit log
├── db/                          Provider abstraction (Supabase | Neon), pure sync, pgvector-backed semantic search
├── knowledge/rag/               RAG pipeline
│   ├── indexer.py               Startup indexer (populates semantic_memory)
│   ├── chunker.py               LlamaIndex SentenceSplitter wrapper
│   ├── ingest.py                Chunk + store long-form documents with citation metadata
│   └── sample_docs/             Bundled sample long-form doc (chunked-RAG demo)
├── rxapp/                       Reflex UI (state, pages, styles)
├── schema/                      Typed domain models per asset category
├── tools/
│   ├── db.py                    Sync CRUD wrappers over db provider
│   ├── schemas.py               Pydantic input schemas (single source)
│   ├── langchain_tools.py       17 shared @tool wrappers (14 CRUD + recall_knowledge/remember_fact/recall_facts)
│   └── stdio_server.py          MCP stdio server for the CLI subprocess
├── eval/                        Eval harness (mechanical + LLM-as-judge) + scenarios + regression diff
│   ├── run_eval.py              Runs scenarios.json, writes results.json + eval/history/ snapshot
│   ├── judge.py                 LLM-as-judge groundedness/relevance scoring
│   └── compare.py               Diffs results.json against the last committed baseline
├── scripts/                     Utility CLIs
│   ├── verify_audit_log.py      Verify the audit log's tamper-evident hash chain
│   ├── migrate_pgvector.py      Re-embed + re-index semantic_memory with pgvector
│   └── check_prompt_version_bump.py  CI check: prompt changes must bump front-matter version
├── tests/                       Cross-cutting tests (memory, guardrails, audit chain, rate limiting, RAG ingest)
├── docs/architecture-decisions/ ADRs (e.g. why LangGraph over Semantic Kernel)
├── .github/workflows/           CI: ci.yml (tests + secrets scan + prompt check), eval-nightly.yml
├── infra/
│   ├── langfuse-compose.yaml    Local self-hosted Langfuse stack
│   └── env.langgraph.example    Annotated env var reference
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── rxconfig.py                  Reflex frontend/backend port config
└── db_init.py                   Bootstrap: schema, RAG index
```

## Quick start

### Prerequisites

- Python ≥ 3.13
- [uv](https://docs.astral.sh/uv) (recommended) or `pip`
- Node.js 20+ (Reflex will install its own frontend deps into `.web/`)
- Postgres (Neon free tier or Supabase free tier is fine)

### 1. Install

```bash
git clone https://github.com/masoudraimi/home-asset-agent
cd home-asset-agent
uv sync           # or: python -m venv .venv && .venv/Scripts/pip install -e .
```

### 2. Configure `.env`

Copy the annotated reference and edit:

```bash
cp infra/env.langgraph.example .env
```

Minimum viable — pick **one** LLM provider:

```env
# Option A — cheapest, cross-model:
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-...
LLM_MODEL_FAST=anthropic/claude-haiku-4-5
LLM_MODEL_SMART=anthropic/claude-sonnet-4-6

# Option B — direct Anthropic:
LLM_PROVIDER=claude_sdk
ANTHROPIC_API_KEY=sk-ant-...

# Option C — Claude Code OAuth (no API key; local dev only):
LLM_PROVIDER=claude_cli   # `claude auth login` first

# Database — pick one (both Neon and Supabase support the pgvector
# extension the schema needs; `ensure_schema()` runs `CREATE EXTENSION IF
# NOT EXISTS vector` for you, but your DB role needs privileges to do so):
DB_PROVIDER=neon                       # or supabase
DATABASE_URL=postgresql://...          # or SUPABASE_URL + SUPABASE_KEY

# Optional but recommended:
CHECKPOINTER=sqlite                    # memory | sqlite | postgres
LANGCHAIN_TRACING_V2=true              # LangSmith
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=home-asset-agent-dev
VOYAGE_API_KEY=pa-...                  # real RAG embeddings — without this,
                                        # retrieval degrades to a hash stub
                                        # (loudly logged, not silent — see
                                        # RAG architecture)
```

### 3. First run

```bash
uv run reflex init                     # one-time — installs frontend deps
uv run reflex run
```

Open [http://localhost:3000](http://localhost:3000). The backend runs on 8001.

An admin account is auto-provisioned via env vars (`ADMIN_EMAIL` + `ADMIN_PASSWORD`) — check the boot log for the exact bootstrap message.

### 4. Test drive

Try these in the chat:

- `"list my HVAC assets"` — routes to the asset specialist
- `"when's my next service?"` — routes to maintenance
- `"how much did I spend on the car this year?"` — routes to insights
- `"give me a full home report"` — parallel fan-out across maintenance + insights
- `"delete house gutters id 4"` — approval card appears via `interrupt()`, click **Confirm** to execute

If you set `LANGCHAIN_TRACING_V2=true`, every turn appears in LangSmith as one root span with nested branches per specialist and per tool.

## Configuration reference

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `claude_cli` | `claude_cli` \| `claude_sdk` \| `openrouter` |
| `LLM_MODEL_FAST` | provider default | Override the "haiku" tier (orchestrator classifier) |
| `LLM_MODEL_SMART` | provider default | Override the "sonnet" tier (specialists) |
| `ANTHROPIC_API_KEY` | — | Required for `claude_sdk` |
| `OPENROUTER_API_KEY` | — | Required for `openrouter` |
| `DB_PROVIDER` | `neon` | `neon` \| `supabase` |
| `DATABASE_URL` | — | Postgres URL (Neon path) |
| `SUPABASE_URL`, `SUPABASE_KEY` | — | Supabase alternative |
| `CHECKPOINTER` | `memory` | `memory` \| `sqlite` \| `postgres` |
| `LANGCHAIN_TRACING_V2` | `false` | Enable LangSmith trace shipping |
| `LANGCHAIN_API_KEY` | — | LangSmith API key |
| `LANGCHAIN_PROJECT` | — | LangSmith project name |
| `LANGFUSE_HOST` | — | Alternative to LangSmith (self-hosted) |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | — | Langfuse credentials |
| `VOYAGE_API_KEY` | — | Real RAG embeddings; falls back to a loudly-logged hash stub (see [RAG architecture](#rag-architecture)) |
| `APP_ENV` | `dev` | `dev` (coloured console logs) \| `prod` (JSON logs) |
| `LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |
| `ALERT_MIN_SEVERITY` | `error` | Minimum severity that fires Discord/Slack alerts |
| `DISCORD_WEBHOOK_URL` | — | Real-time alerts channel |
| `SLACK_WEBHOOK_URL` | — | Real-time alerts channel |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | — | Bootstrap admin on first run |

Full annotated list in [infra/env.langgraph.example](infra/env.langgraph.example).

### Per-agent knobs (`agents/*/agent.yaml`, not env vars)

| Key | Default | Purpose |
|---|---|---|
| `retrieve_semantic` | `false` | Run the auto-RAG `retrieve` node before every `llm` call (all three specialists have this `true`) |
| `rate_limit_per_min` | `30` | Token-bucket refill rate for this agent, per user |
| `rate_limit_burst` | `10` | Token-bucket capacity (max burst before throttling) |
| `budget_usd` | — | Per-turn USD cost cap |
| `max_turns` | `20` | Per-turn tool-call iteration cap |
| `guardrails.pii_detection` | `false` | PII redaction on this agent's output (uniformly `true` for all four agents as of this revision) |
| `guardrails.prompt_injection` | `true` | Regex injection layer |
| `guardrails.injection_classifier` | `true` | Escalate to the LLM classifier when the regex layer is clean |
| `guardrails.max_output_chars` | `16000` | Output truncation length |

## Running

### Development

```bash
uv run reflex run
# frontend: http://localhost:3000
# backend:  http://localhost:8001
```

Hot-reload works on Python file changes. `data/audit.log` uses `.log` (not `.jsonl`) because Granian's file watcher would otherwise treat every audit write as a code change.

### Production (Docker)

```bash
docker compose up -d
```

Reflex `--env prod` behind ports 3000 (frontend) and 8001 (backend). Note that `claude_cli` won't work inside a container — use `claude_sdk` or `openrouter` for the container path.

### Self-hosted observability

For offline dev without a LangSmith account:

```bash
docker compose -f infra/langfuse-compose.yaml up -d
# Langfuse UI at http://localhost:3001
# Create a project, copy the keys into .env:
#   LANGFUSE_HOST=http://localhost:3001
#   LANGFUSE_PUBLIC_KEY=pk-lf-...
#   LANGFUSE_SECRET_KEY=sk-lf-...
```

## Testing

```bash
uv run pytest agents/asset/tests/ \
              agents/maintenance/tests/test_maintenance_graph.py \
              agents/insights/tests/ \
              agents/orchestrator/tests/test_dispatcher.py \
              tests/                                                -q
```

118 tests, all offline (stub/fake LLMs and providers), no API keys required — this is also what `.github/workflows/ci.yml` runs on every PR. Coverage:

- **Structural** — every graph compiles with correct topology (including the `retrieve` / `guardrail_tool_output` / rate-limit nodes)
- **Behavioural** — direct answers, guardrail block, feature-flag dispatch, tool_call → tool_result event stream, adapter routing/metrics
- **Interrupt** — pause + resume with approved / cancelled paths for `delete_asset`
- **Dispatcher** — single-route passthrough, compound parallel fan-out, injection short-circuit, one-specialist-error-others-survive
- **Memory** — remember_fact / recall_facts round-trip, recall_knowledge cross-agent, Voyage → stub fallback, pgvector-shaped SQL contract, token-budget-aware short-term trimming
- **Security** — layered injection defense (regex + classifier), PII redaction, tamper-evident audit hash chain, rate limiting, tool-level role authorization
- **RAG** — chunking + ingestion pipeline, auto-retrieval citation shaping
- **Orchestration breadth** — Deep Agents research tool, PydanticAI structured report tool (both mocked at the framework boundary — no real model calls)

## Evaluation

[eval/run_eval.py](eval/run_eval.py) is a real-API integration eval — it requires `VOYAGE_API_KEY`, `ANTHROPIC_API_KEY` (or `OPENROUTER_API_KEY`), and a live `DATABASE_URL` seeded with data matching [eval/scenarios.json](eval/scenarios.json)'s expectations, so it's not part of the offline unit test suite above.

```bash
uv run python eval/run_eval.py      # scores every scenario, writes eval/results.json + a dated snapshot under eval/history/
uv run python eval/compare.py       # diffs the new results.json against the last committed one
```

19 scenarios across simple/moderate/complex tiers, including 4 RAG-specific scenarios ([knowledge/rag/](knowledge/rag/) auto-retrieval + chunked-document retrieval + a negative case with nothing indexed). Each scenario is scored two ways:

- **Mechanical** (the pass/fail gate) — expected tool calls used, and a keyword-overlap check on the final answer.
- **LLM-as-judge** ([eval/judge.py](eval/judge.py), additive signal only — never gates `passed`, so a flaky judge call can't silently fail an otherwise-correct scenario) — groundedness and relevance scored 1–5 by a cheap model call.

`eval/results.json` is committed as a real regression baseline (previously gitignored, so there was nothing to diff against) — `eval/compare.py` reports per-tier accuracy deltas and per-scenario pass/fail flips against it.

## Continuous integration

[.github/workflows/ci.yml](.github/workflows/ci.yml) runs on every PR and push to `main`:

- **test** — the full offline unit test suite (see [Testing](#testing) above).
- **secrets-scan** — [gitleaks](https://github.com/gitleaks/gitleaks) over the full history.
- **prompt-version-check** — [scripts/check_prompt_version_bump.py](scripts/check_prompt_version_bump.py) fails the PR if a `agents/*/prompts/system.md` changed without its front-matter `version:` being bumped.

[.github/workflows/eval-nightly.yml](.github/workflows/eval-nightly.yml) runs the real-API eval (above) on a nightly cron plus `workflow_dispatch`, uploading `eval/results.json` and `eval/history/` as a build artifact — kept off the per-PR workflow deliberately, so real LLM/embedding cost never lands on every push. Needs `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, and `EVAL_DATABASE_URL` as repo secrets.

## Debugging

- **Recent audit events**: `python scripts/replay.py --list --limit=50`
- **One request by ID**: `python scripts/replay.py req_<hex>`
- **Verify the audit log hasn't been tampered with**: `python scripts/verify_audit_log.py` — exits nonzero and names the first broken line if the hash chain is broken.
- **Duplicate detection**: `python scripts/dedupe_assets.py`
- **Re-embed semantic memory with real embeddings**: `python scripts/migrate_pgvector.py --apply` (after setting `VOYAGE_API_KEY`).
- **Live traces**: LangSmith UI (or Langfuse UI at `LANGFUSE_HOST`) — search by `request_id` metadata.
- **Structured logs**: JSON to stdout in prod (`APP_ENV=prod`), coloured in dev. All lines carry `request_id` + `user_id`; `llm_finished` also carries `prompt_version` (see prompt front-matter in `agents/*/prompts/system.md`).

## Extending

- **Add a tool**: add a Pydantic schema to [tools/schemas.py](tools/schemas.py), a `@tool` wrapper in [tools/langchain_tools.py](tools/langchain_tools.py), and a matching function in [tools/db.py](tools/db.py). The `stdio_server` and `TOOLS` list pick it up automatically.
- **Add a specialist**: create `agents/<name>/{agent.yaml,prompts/system.md,graph.py}` using the existing three as templates. Add its name to the `classify_intent` prompt in [agents/orchestrator/workflows/routing.py](agents/orchestrator/workflows/routing.py) and to the dispatch map in [agents/orchestrator/agent.py](agents/orchestrator/agent.py). Add YAML front-matter (`version`, `last_updated`, `changelog`) to its system prompt — `agents/_specialist.py::_load_system_prompt` strips it before the LLM sees it.
- **Add a DB provider**: implement the `DBProvider` protocol from [db/base.py](db/base.py) (including the pgvector-backed `semantic_store`/`semantic_search`/`semantic_count` methods); register in [db/__init__.py](db/__init__.py); set `DB_PROVIDER=<name>`.
- **Add an audit event type**: extend `AUDIT_EVENT_TYPES` in [core/audit.py](core/audit.py) and call `audit("<name>", …)` from the relevant graph node — it's automatically hash-chained.
- **Add a metric**: register a Prometheus counter/histogram in [core/metrics.py](core/metrics.py) with a stable label set.
- **Tune rate limits or PII/injection coverage**: per-agent knobs live in `agent.yaml:rate_limit_per_min`/`rate_limit_burst`/`guardrails.*` — see [Per-agent knobs](#per-agent-knobs-agentsagentyaml-not-env-vars). New PII patterns go in [core/guardrails.py](core/guardrails.py); new injection heuristics can go in the regex there or in the classifier prompt in [core/injection_classifier.py](core/injection_classifier.py).
- **Ingest a long-form document into RAG**: `knowledge.rag.ingest.ingest_document(agent_name=..., source_name=..., text=..., doc_type="manual")` — chunks + stores with citation metadata. See [knowledge/rag/sample_docs/](knowledge/rag/sample_docs/) for the pattern.

## Provider paths — deeper dive

The runtime dispatches on `LLM_PROVIDER` at [agent/runner.py::_use_cli](agent/runner.py):

| Provider | Runtime | Auth | Interrupt approval | Notes |
|---|---|---|---|---|
| `claude_cli` | Claude Code CLI subprocess ([agent/cli_runner.py](agent/cli_runner.py)) | OAuth via `claude auth login` — no API key | EventBus → `__approval_confirmed__` sentinel | Bypasses LangGraph. Best for local dev on a Claude Code subscription |
| `claude_sdk` | LangGraph specialists + [`ChatAnthropic`](https://python.langchain.com/api_reference/anthropic/) | `ANTHROPIC_API_KEY` | Native `interrupt()` + `Command(resume=...)` | Direct API |
| `openrouter` | LangGraph specialists + [`ChatOpenAI`](https://python.langchain.com/api_reference/openai/) pointed at OpenRouter | `OPENROUTER_API_KEY` | Native `interrupt()` + `Command(resume=...)` | Any [OpenRouter model](https://openrouter.ai/models); `LLM_MODEL_*` overrides per tier |

## Error handling

Config and runtime errors surface as actionable UI messages instead of stack traces. See [agent/langgraph_adapter.py::_classify_error_for_ui](agent/langgraph_adapter.py):

- `MissingCredentialsError` → `⚠  Configuration error: LLM_PROVIDER=openrouter but OPENROUTER_API_KEY is not set. …`
- 429 → `⚠  Rate limited by the upstream model provider. Try again in a minute, or switch to a different model — set LLM_MODEL_SMART=… in your .env and restart.` (this is the *provider's* rate limit — Anthropic/OpenRouter returning 429; the app's own per-`(user, agent)` limiter in [core/rate_limit.py](core/rate_limit.py) is a separate, earlier gate that terminates with `outcome:rate_limited` before any LLM call is made.)
- 401/403 → `⚠  Authentication error (401): check OPENROUTER_API_KEY / ANTHROPIC_API_KEY in .env.`
- Everything else → generic message + full stack trace in structured logs (never lost).

## License

Personal project. Portions of the setup are inspired by public Reflex, LangGraph, and Anthropic examples.
