# WiseWombat — Multi-Agent Home Asset Management

[![Python](https://img.shields.io/badge/python-%3E%3D3.13-3776AB?logo=python&logoColor=white)](https://python.org)
[![uv](https://img.shields.io/badge/uv-package%20manager-DE5FE9)](https://docs.astral.sh/uv)
[![Reflex](https://img.shields.io/badge/Reflex-%3E%3D0.9-5646ED?logo=reflex&logoColor=white)](https://reflex.dev)
[![LangGraph](https://img.shields.io/badge/LangGraph-%3E%3D1.2-1C3C3C)](https://langchain-ai.github.io/langgraph/)
[![LangChain](https://img.shields.io/badge/LangChain-1.5-1C3C3C)](https://python.langchain.com)
[![Claude](https://img.shields.io/badge/Claude-Sonnet%204.6%20%2F%20Haiku%204.5-D97757)](https://anthropic.com)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-compatible-74AA9C)](https://openrouter.ai)
[![LangSmith](https://img.shields.io/badge/LangSmith-tracing-1C3C3C)](https://smith.langchain.com)
[![Langfuse](https://img.shields.io/badge/Langfuse-self%E2%80%91hostable-1B7BF7)](https://langfuse.com)
[![Neon](https://img.shields.io/badge/Neon-Postgres-00E699?logo=neon&logoColor=black)](https://neon.tech)
[![Supabase](https://img.shields.io/badge/Supabase-Postgres-3ECF8E?logo=supabase&logoColor=white)](https://supabase.com)
[![pytest](https://img.shields.io/badge/pytest-%3E%3D9-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org)

A conversational AI agent for tracking home assets, maintenance, and spend. Ask plain-language questions about your appliances, HVAC, plumbing, vehicles, plants and trees — the agent chooses the right specialist, calls the right tools, and pauses for human approval before destructive actions.

Built as a working household tool **and** a portfolio piece for modern agent architecture: **LangGraph state machines**, **human-in-the-loop via `interrupt()`**, **provider-agnostic LLM factory** (Anthropic / OpenRouter / Claude Code CLI with OAuth), **first-class observability** (LangSmith / Langfuse / Prometheus / structured audit), and a **layered core** that separates orchestration, specialists, tools, memory, and the DB provider.

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
   │ + OAuth (no key)  │                       │  ┌─────────────────────────┐
   │ + EventBus for    │                       │  │  LangGraph specialist   │
   │   approvals       │                       │  │  ────────────────────   │
   │ + __approval_     │                       │  │  enter                  │
   │   confirmed__     │                       │  │   → guardrail_in        │
   │   sentinel        │                       │  │   → llm ↔ tools ─┐      │
   └───────────────────┘                       │  │              [handle_   │  asset only
                                               │  │              approval] │  interrupt()
                                               │  │   → guardrail_out       │
                                               │  │   → exit (metrics)      │
                                               │  └─────────────────────────┘
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
                                            │  tools/langchain_tools │  17 @tool wrappers
                                            │      (uses tools/db.py │  (14 CRUD + 3 memory)
                                            │      + tools/schemas)  │
                                            └───────────┬────────────┘
                                                        ▼
                                     ┌───────────────────────────────────────┐
                                     │  db/ provider — Supabase | Neon       │  user-scoped
                                     └───────────────────────────────────────┘
```

### Core primitives

| Concern | Module | Notes |
|---|---|---|
| Structured logs | [core/logging.py](core/logging.py) | structlog JSON in prod, colour console in dev; contextvar-based correlation IDs; PII redaction |
| Metrics | [core/metrics.py](core/metrics.py) | 8 Prometheus counters/histograms + in-memory ring buffer for the admin UI |
| Audit trail | [core/audit.py](core/audit.py) | Pydantic-validated JSONL, whitelisted event types, weekly gzip rotation |
| Alerts | [core/alerts.py](core/alerts.py) | Discord/Slack webhooks with severity filtering |
| Guardrails | [core/guardrails.py](core/guardrails.py) | Regex injection detection + PII sanitisation + output truncation |
| Sessions | [core/session.py](core/session.py) | `contextvars.ContextVar` for per-request user scoping (async + subprocess) |
| Checkpointer | [core/checkpointer.py](core/checkpointer.py) | In-memory / SQLite / Postgres factory (LangGraph state persistence) |
| LLM factory | [core/llm.py](core/llm.py) | Provider selection; explicit `MissingCredentialsError` on misconfig |
| Pricing | [core/pricing.py](core/pricing.py) | Per-model USD rate table for the budget guard |
| Memory | [core/memory/](core/memory/) | short-term (context), long-term (per-user KV), semantic (RAG with Voyage/hash-stub) |

### Specialist graphs share one builder

All three specialists are compiled by [`SpecialistGraph`](agents/_specialist.py) with the same shape:

```
START → enter → guardrail_in → llm ⇄ tools → guardrail_out → exit → END
                                      │
                                      └─► handle_approval (asset only, interrupt())
```

Loop-engineering rules applied to every node:

- **Retries**: tenacity, 3 attempts, exp-backoff 1–8s. Config errors (`MissingCredentialsError`) + upstream 401/403/429 skip retry to fail fast with an actionable message.
- **Max iterations**: enforced from `agent.yaml:max_turns` (asset=25, maintenance=20, insights=15, orchestrator=5).
- **Budget**: per-turn `budget_usd` cap from `agent.yaml`. `core/pricing.py` accumulates cost from `usage_metadata`; over-budget terminates with `outcome:budget`.
- **Timeouts**: 30s LLM / 10s tool via `RunnableLambda.with_config`.
- **Termination reason**: always set at exit (`ok` | `budget` | `max_iter` | `guardrail` | `error`), emitted in metrics.

### Human-in-the-loop

Destructive `delete_asset` runs through a two-step gate:

1. LLM calls `review_delete_asset(id)` → tool returns payload with asset details and cascade count.
2. Router detects `approval_requested`, sends state to `handle_approval` node.
3. `handle_approval` calls LangGraph `interrupt(payload)` — graph **pauses**, state persists in checkpointer.
4. Reflex renders an Approval Card; the adapter surfaces a `pending_approval` UI event with `thread_id`.
5. User clicks **Confirm** → Reflex calls `resume_graph_turn(thread_id, approved=True)` → LangGraph resumes `handle_approval`.
6. `handle_approval` executes `db.delete_asset` **directly** (no extra LLM tokens), writes three audit events, produces the confirmation message.

## Tech stack

**Runtime**

- [Reflex ≥ 0.9](https://reflex.dev) — Python full-stack (React frontend + FastAPI backend). Vite dev server on 3000, WebSocket backend on 8001.
- [LangGraph ≥ 1.2](https://langchain-ai.github.io/langgraph/) — state-graph orchestration, native `interrupt()` HITL, checkpointers.
- [LangChain Core 1.5](https://python.langchain.com) — `@tool` decorators + ChatModel abstraction bound to the specialists.
- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python) + [langchain-anthropic](https://pypi.org/project/langchain-anthropic/) — `ChatAnthropic`.
- [OpenAI SDK](https://github.com/openai/openai-python) + [langchain-openai](https://pypi.org/project/langchain-openai/) — `ChatOpenAI` pointed at OpenRouter for cross-provider models.
- [Claude Code CLI](https://docs.claude.com/en/docs/claude-code) — subprocess mode, OAuth-based auth for the `claude_cli` provider path.
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) — stdio server exposing tools to the CLI subprocess.

**Data layer**

- [Neon](https://neon.tech) or [Supabase](https://supabase.com) Postgres (interchangeable — pick with `DB_PROVIDER`).
- [psycopg 3](https://www.psycopg.org/psycopg3/) (Neon path), [supabase-py](https://github.com/supabase/supabase-py) (Supabase path).
- [Pydantic v2](https://docs.pydantic.dev) — schemas for every tool input and every domain category (see `schema/`).

**Observability**

- [structlog 26](https://www.structlog.org) — JSON logs with contextvar-based correlation IDs (`request_id`, `thread_id`, `user_id`, `trace_id`, `agent`).
- [prometheus_client](https://github.com/prometheus/client_python) — 8 turn/tool/guardrail/budget/checkpoint metrics.
- [LangSmith](https://smith.langchain.com) *or* self-hosted [Langfuse](https://langfuse.com) — per-turn root span with parallel branches per specialist.
- [tenacity](https://tenacity.readthedocs.io) — exponential-backoff retries with config-error exclusions.

**Auth / infrastructure**

- [bcrypt](https://pypi.org/project/bcrypt/) — password hashing for admin users.
- [python-dotenv](https://github.com/theskumar/python-dotenv) — env loading.
- [Docker](https://docker.com) + [uv](https://docs.astral.sh/uv) — deployment.

**Optional**

- [Voyage AI](https://voyageai.com) `voyage-3.5-lite` — semantic embeddings (falls back to a deterministic hash stub if `VOYAGE_API_KEY` isn't set).

## Repository layout

```
home-asset-agent/
├── agent/                       Runtime router
│   ├── runner.py                run_turn (sync) / run_turn_in_loop (async); routes by LLM_PROVIDER
│   ├── cli_runner.py            Claude Code CLI subprocess dispatch (OAuth path)
│   └── langgraph_adapter.py     graph events → UI event dicts + interrupt/resume + error classifier
├── agents/                      Multi-agent architecture
│   ├── state.py                 Shared AgentState TypedDict
│   ├── _specialist.py           SpecialistGraph builder (300 lines, used by all 3)
│   ├── asset/       ← inventory, onboarding, delete-with-approval
│   ├── maintenance/ ← scheduling, plant care, Telegram digest
│   ├── insights/    ← spend analytics, warranty alerts
│   └── orchestrator/
│       ├── dispatcher.py        Functional dispatch (classify → parallel fan-out → merge, @traceable)
│       ├── agent.py             Thin _run_specialist_events helper
│       └── workflows/routing.py Haiku-backed intent classifier
├── core/                        Cross-cutting primitives (see table above)
├── db/                          Provider abstraction (Supabase | Neon), pure sync
├── knowledge/rag/               Startup RAG indexer (populates semantic_memory)
├── rxapp/                       Reflex UI (state, pages, styles)
├── schema/                      Typed domain models per asset category
├── tools/
│   ├── db.py                    Sync CRUD wrappers over db provider
│   ├── schemas.py               Pydantic input schemas (single source)
│   ├── langchain_tools.py       17 @tool wrappers (14 CRUD + recall_knowledge/remember_fact/recall_facts)
│   └── stdio_server.py          MCP stdio server for the CLI subprocess
├── eval/                        Benchmark harness + scenarios
├── scripts/                     Utility CLIs (replay, dedupe, monthly reminder)
├── tests/                       Cross-cutting tests (memory tools)
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

# Database — pick one:
DB_PROVIDER=neon                       # or supabase
DATABASE_URL=postgresql://...          # or SUPABASE_URL + SUPABASE_KEY

# Optional but recommended:
CHECKPOINTER=sqlite                    # memory | sqlite | postgres
LANGCHAIN_TRACING_V2=true              # LangSmith
LANGCHAIN_API_KEY=lsv2_pt_...
LANGCHAIN_PROJECT=home-asset-agent-dev
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
| `VOYAGE_API_KEY` | — | Real embeddings; falls back to hash stub |
| `APP_ENV` | `dev` | `dev` (coloured console logs) \| `prod` (JSON logs) |
| `LOG_LEVEL` | `INFO` | `DEBUG` \| `INFO` \| `WARNING` \| `ERROR` |
| `ALERT_MIN_SEVERITY` | `error` | Minimum severity that fires Discord/Slack alerts |
| `DISCORD_WEBHOOK_URL` | — | Real-time alerts channel |
| `SLACK_WEBHOOK_URL` | — | Real-time alerts channel |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | — | Bootstrap admin on first run |

Full annotated list in [infra/env.langgraph.example](infra/env.langgraph.example).

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
              agents/insights/tests/test_insights_graph.py \
              agents/orchestrator/tests/test_dispatcher.py \
              tests/                                                -q
```

28 tests, all offline (mocked LLM), no API keys required. Coverage:

- **Structural** — every graph compiles with correct topology
- **Behavioural** — direct answers, guardrail block, feature-flag dispatch, tool_call → tool_result event stream, adapter routing/metrics
- **Interrupt** — pause + resume with approved / cancelled paths for `delete_asset`
- **Dispatcher** — single-route passthrough, compound parallel fan-out, injection short-circuit, one-specialist-error-others-survive
- **Memory** — remember_fact / recall_facts round-trip, recall_knowledge cross-agent, Voyage → stub fallback

## Debugging

- **Recent audit events**: `python scripts/replay.py --list --limit=50`
- **One request by ID**: `python scripts/replay.py req_<hex>`
- **Duplicate detection**: `python scripts/dedupe_assets.py`
- **Live traces**: LangSmith UI (or Langfuse UI at `LANGFUSE_HOST`) — search by `request_id` metadata.
- **Structured logs**: JSON to stdout in prod (`APP_ENV=prod`), coloured in dev. All lines carry `request_id` + `user_id`.

## Extending

- **Add a tool**: add a Pydantic schema to [tools/schemas.py](tools/schemas.py), a `@tool` wrapper in [tools/langchain_tools.py](tools/langchain_tools.py), and a matching function in [tools/db.py](tools/db.py). The `stdio_server` and `TOOLS` list pick it up automatically.
- **Add a specialist**: create `agents/<name>/{agent.yaml,prompts/system.md,graph.py}` using the existing three as templates. Add its name to the `classify_intent` prompt in [agents/orchestrator/workflows/routing.py](agents/orchestrator/workflows/routing.py) and to the dispatch map in [agents/orchestrator/agent.py](agents/orchestrator/agent.py).
- **Add a DB provider**: implement the `DBProvider` protocol from [db/base.py](db/base.py); register in [db/__init__.py](db/__init__.py); set `DB_PROVIDER=<name>`.
- **Add an audit event type**: extend `AUDIT_EVENT_TYPES` in [core/audit.py](core/audit.py) and call `audit("<name>", …)` from the relevant graph node.
- **Add a metric**: register a Prometheus counter/histogram in [core/metrics.py](core/metrics.py) with a stable label set.

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
- 429 → `⚠  Rate limited by the upstream model provider. Try again in a minute, or switch to a different model — set LLM_MODEL_SMART=… in your .env and restart.`
- 401/403 → `⚠  Authentication error (401): check OPENROUTER_API_KEY / ANTHROPIC_API_KEY in .env.`
- Everything else → generic message + full stack trace in structured logs (never lost).

## License

Personal project. Portions of the setup are inspired by public Reflex, LangGraph, and Anthropic examples.
