# Multi-Agent Home Asset Management System

[![Python](https://img.shields.io/badge/python-%3E%3D3.13-3776AB?logo=python&logoColor=white)](https://python.org)
[![uv](https://img.shields.io/badge/uv-package%20manager-DE5FE9)](https://docs.astral.sh/uv)
[![Streamlit](https://img.shields.io/badge/Streamlit-%3E%3D1.58-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![Claude](https://img.shields.io/badge/Claude-Sonnet%204.6%20%2F%20Haiku%204.5-D97757)](https://anthropic.com)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-compatible-74AA9C)](https://openrouter.ai)
[![MCP](https://img.shields.io/badge/MCP-11%20tools-6E40C9)](https://modelcontextprotocol.io)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063)](https://docs.pydantic.dev)
[![Neon](https://img.shields.io/badge/Neon-database-00E699?logo=neon&logoColor=black)](https://neon.tech)
[![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-tracing-425CC7?logo=opentelemetry&logoColor=white)](https://opentelemetry.io)
[![pytest](https://img.shields.io/badge/pytest-%3E%3D9.0-0A9EDC?logo=pytest&logoColor=white)](https://docs.pytest.org)

A conversational AI agent for managing home assets and maintenance. Track appliances, HVAC, plumbing, vehicles, plants, and more — then ask plain-language questions about warranties, service history, upcoming tasks, and spend analytics.

Built as both a functional personal tool and a portfolio demonstration of **multi-agent orchestration**, **agentic tool use**, **LLM-as-judge workflows**, and **provider-agnostic design** with the Claude Agent SDK and OpenRouter.


## Demo

```
You:   Add my dishwasher.
Agent: [calls get_onboarding_questions]
       Let's get your dishwasher set up. What brand and model is it?

You:   Bosch Series 6, bought it in March 2023 for $1,200.
Agent: [calls review_asset_draft] → confidence: high, ready_to_save: true
       Here's the summary: does this look right?
         Name: Dishwasher, Brand: Bosch, Model: Series 6
         Purchase date: 2023-03-01, Price: $1,200

You:   Yes.
Agent: [calls add_asset]
       Saved. Also, your HVAC filter replacement is 12 days overdue.
```


## Architecture

```
Streamlit UI
      │
      ▼
OrchestratorAgent          intent classification (Claude Haiku)
      │
      ├─► AssetAgent        inventory, onboarding, suggestions (Claude Sonnet)
      │         └── workflows/onboarding.py   LLM-as-judge draft review
      │
      ├─► MaintenanceAgent  scheduling, plant care, Telegram digest (Claude Sonnet)
      │         └── workflows/telegram.py     push reminders
      │
      └─► InsightsAgent     spend analytics, warranty alerts (Claude Sonnet)

Shared infrastructure (core/)
  ├── BaseAgent          provider-aware agent loop (Claude SDK ↔ OpenRouter)
  ├── AgentRegistry      loads agent.yaml configs at startup
  ├── ConversationContext sliding-window memory + working memory hints
  ├── Guardrails         input injection detection + output sanitisation
  ├── EventBus           HumanApprovalRequested → Streamlit confirmation cards
  └── OTel tracing       per-turn spans with token/latency/tool-call attributes

Tools (tools/mcp_server.py)
  11 MCP tools: add, list, search, update assets;
  log and query maintenance; onboarding questions; plant care; spend insights
```

### Agent models

| Agent | Model | Role |
|---|---|---|
| Orchestrator | Claude Haiku | Intent classification and routing |
| Asset | Claude Sonnet | Inventory management and onboarding |
| Maintenance | Claude Sonnet | Scheduling and plant care |
| Insights | Claude Sonnet | Spend analytics and warranty alerts |
| Onboarding judge | Claude Haiku | LLM-as-judge completeness review |



## Provider Switching

The agent loop and all LLM calls are provider-agnostic. Switch at runtime via a single env var:

```bash
LLM_PROVIDER=claude_cli    # default
LLM_PROVIDER=claude_sdk
LLM_PROVIDER=openrouter
```

| Provider | Env var required | How it works |
|---|---|---|
| `claude_sdk` | `ANTHROPIC_API_KEY` | `claude_agent_sdk.query()`: runs the `claude` binary via the Python SDK with an in-process MCP server |
| `claude_cli` | authenticated `claude` CLI | spawns `claude --output-format stream-json` as a subprocess; tools are served by a separate stdio MCP process (`tools/stdio_server.py`) |
| `openrouter` | `OPENROUTER_API_KEY` | OpenAI-compatible HTTP API; agent loop and tool dispatch are handled entirely in-process |

### How each path works

```text
claude_sdk     Python → claude_agent_sdk.query() → claude binary (subprocess)
                                                         └── in-process MCP server

claude_cli     Python → asyncio subprocess (claude CLI)
                             └── --mcp-config → tools/stdio_server.py (stdio MCP subprocess)

openrouter     Python → openai.AsyncOpenAI → https://openrouter.ai/api/v1
                             └── tool_calls → dispatch_tool() in-process
```

Model IDs are resolved per-provider in `core/models.py` via `resolve_model()`. The `agent.yaml` files always store Anthropic-native IDs; `resolve_model()` translates to OpenRouter's namespace when needed.



## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Claude Sonnet 4.6 / Haiku 4.5 |
| Agent framework (default) | Claude Agent SDK + in-process MCP |
| Agent framework (alternate) | OpenAI SDK → OpenRouter |
| Database | PostgreSQL (Neon by default; Supabase supported) |
| Tool protocol | MCP (Model Context Protocol) |
| Data validation | Pydantic v2 |
| UI | Streamlit |
| Observability | OpenTelemetry |
| Dependency management | uv |



## Key Patterns Demonstrated

**Multi-agent orchestration**: the orchestrator classifies intent with a lightweight Haiku call and fans out to one or more specialist agents. Complex queries (e.g. "full home health report") dispatch to multiple agents concurrently.

**LLM-as-judge**: before saving a new asset, `review_asset_draft` calls Haiku to score completeness, flag suspicious values, and surface missing fields. The agent only calls `add_asset` after the user confirms.

**Human-in-the-loop**: `HumanApprovalRequested` events flow through the `EventBus` to render a confirmation card in the Streamlit UI before any write is committed.

**Working memory**: `ConversationContext` tracks asset names and IDs seen in tool results and injects them as a hint on subsequent turns, reducing redundant lookups.

**Provider abstraction**: `core/models.py` exposes `simple_complete()` and `resolve_model()` so callers never hard-code a provider. `BaseAgent` branches between `_run_cli()`, `_run_sdk()`, and `_run_openrouter()` based on `LLM_PROVIDER`.

**MCP tools**: all 11 tools are defined once in `tools/mcp_server.py` with Pydantic schemas. The same definitions generate both the in-process MCP server (Claude SDK path) and OpenAI function-calling schemas (OpenRouter path).



## Getting Started

### Prerequisites

- Python 3.13+
- `uv` package manager
- A PostgreSQL database — [Neon](https://neon.tech) (default, free tier) or [Supabase](https://supabase.com)
- LLM provider (pick one):
  - **Claude CLI** (default): `claude` CLI installed and authenticated (`claude login`)
  - **Claude SDK**: `ANTHROPIC_API_KEY` in `.env`
  - **OpenRouter**: `OPENROUTER_API_KEY` in `.env`

### 1. Set up the database

The app applies the schema automatically on first launch — no manual SQL required.

**Neon (default):**

1. Create a free project at [neon.tech](https://neon.tech)
2. Copy the connection string from the Neon console (Dashboard → Connection Details → Connection string)
3. Set `DATABASE_URL` in `.env` (see step 2)

**Supabase (alternative):**

1. Create a project at [supabase.com](https://supabase.com)
2. Set `DB_PROVIDER=supabase`, `SUPABASE_URL`, and `SUPABASE_KEY` in `.env`
3. Optionally set `SUPABASE_DB_URL` or `SUPABASE_DB_PASSWORD` for automatic schema creation; otherwise paste the schema into the Supabase SQL editor manually

> **Multi-user:** Data is isolated per user at the application layer — every query
> filters by the signed-in user's ID. Accounts are created only by an admin via
> the in-app **Admin** tab; there is no public sign-up. On first run the app
> bootstraps an admin account from `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

### 2. Configure environment variables

```bash
git clone https://github.com/masoudraimi/Multi-Agent-Home-Asset-Management-System
cd Multi-Agent-Home-Asset-Management-System

uv sync
cp .env.example .env   # then fill in your values
```

`.env`:

```env
# ── Database provider ─────────────────────────────────────────────────────────
DB_PROVIDER=neon          # or: supabase

# ── Neon / standard PostgreSQL (used when DB_PROVIDER=neon) ──────────────────
DATABASE_URL=postgresql://user:password@host/dbname?sslmode=require

# ── Supabase (used when DB_PROVIDER=supabase) ─────────────────────────────────
# SUPABASE_URL=https://<your-project-ref>.supabase.co
# SUPABASE_KEY=<your-service-role-key>
# SUPABASE_DB_URL=postgresql://postgres:<pw>@db.<ref>.supabase.co:5432/postgres

# ── Admin bootstrap ───────────────────────────────────────────────────────────
ADMIN_EMAIL=you@example.com
ADMIN_PASSWORD=<choose-a-strong-password>

# ── LLM provider ──────────────────────────────────────────────────────────────
# LLM_PROVIDER=claude_cli    # default — no API key needed if claude CLI is authenticated
# LLM_PROVIDER=claude_sdk
# ANTHROPIC_API_KEY=sk-ant-...
# LLM_PROVIDER=openrouter
# OPENROUTER_API_KEY=sk-or-...

# ── Optional integrations ─────────────────────────────────────────────────────
# TELEGRAM_BOT_TOKEN=...
# TELEGRAM_CHAT_ID=...
```

> **Switching databases:** change `DB_PROVIDER` and supply the matching credentials.
> The schema is applied automatically either way — no manual SQL needed.

### 3. Run the app

```bash
uv run streamlit run app.py
```

On first launch, the app automatically seeds the database with 13 sample assets and 19 maintenance records.

### Run the eval suite

```bash
uv run python eval/run_eval.py
```

Benchmarks cover the orchestrator, asset agent, and maintenance agent across simple / moderate / complex scenarios. Results are saved to `eval/results/` and surfaced in the Observability tab.



## Deploy to Streamlit Community Cloud

1. Push your repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app** → connect your repo
3. Set the entry point to `app.py`
4. Under **Secrets**, add your database and LLM credentials:

```toml
# Neon (default)
DB_PROVIDER = "neon"
DATABASE_URL = "postgresql://user:password@host/dbname?sslmode=require"

# Or Supabase
# DB_PROVIDER = "supabase"
# SUPABASE_URL = "https://<ref>.supabase.co"
# SUPABASE_KEY = "<service-role-key>"

ADMIN_EMAIL = "you@example.com"
ADMIN_PASSWORD = "..."
ANTHROPIC_API_KEY = "sk-ant-..."
```

The schema is applied automatically on first launch. Data persists in your database across deployments.



## Database Schema

**assets**: `id`, `name`, `category`, `brand`, `model`, `serial`, `purchase_date`, `purchase_price`, `warranty_expiry`, `location`, `notes`, `plant_species`, `plant_size`, `planting_date`, `plant_notes`

**maintenance_tasks**: `id`, `asset_id`, `task_name`, `completed_date`, `cost`, `notes`, `next_due_date`, `interval_days`

**agent_memory**: per-agent key-value store for long-term memory

**semantic_memory**: embedding-based RAG store for plant care and asset knowledge

Asset categories: `appliances`, `HVAC`, `plumbing`, `electrical`, `exterior`, `vehicle`, `garden`, `plants_trees`, `other`



## Project Structure

```
home-asset-agent/
├── agents/
│   ├── orchestrator/
│   │   ├── agent.py / agent.yaml / prompts/system.md
│   │   └── workflows/routing.py       intent classification
│   ├── asset/
│   │   ├── agent.py / agent.yaml / prompts/system.md
│   │   └── workflows/onboarding.py    LLM-as-judge asset review
│   │   └── workflows/suggestions.py   missing asset gap analysis
│   ├── maintenance/
│   │   ├── agent.py / agent.yaml / prompts/system.md
│   │   ├── workflows/plant_care.py    species-specific care schedules
│   │   ├── workflows/scheduling.py    overdue task detection
│   │   └── workflows/telegram.py      push digest
│   └── insights/
│       ├── agent.py / agent.yaml / prompts/system.md
│       ├── workflows/spend_analytics.py
│       └── workflows/warranty_alerts.py
├── core/
│   ├── base_agent.py      provider-aware agent loop
│   ├── models.py          Provider enum, resolve_model(), simple_complete()
│   ├── registry.py        AgentRegistry: loads agent.yaml configs
│   ├── memory/            short_term (sliding window), long_term, semantic
│   ├── guardrails.py      injection detection + output sanitisation
│   ├── event_bus.py       publish/subscribe for UI events
│   ├── events.py          event dataclasses (HumanApprovalRequested, etc.)
│   ├── executor.py        WorkflowExecutor (sequential/parallel/retry)
│   ├── session.py         per-user data isolation via contextvars
│   └── observability.py   OTel tracer setup
├── db/
│   ├── base.py            DBProvider protocol (swappable contract)
│   ├── neon.py            NeonProvider: psycopg3 + raw SQL (default)
│   ├── supabase.py        SupabaseProvider: Supabase SDK
│   └── __init__.py        get_provider() factory (reads DB_PROVIDER)
├── schema/
│   ├── __init__.py        central registry: get_questions(), get_checklist(), get_plant_care()
│   ├── models.py          Pydantic models: CategorySchema, PlantCategorySchema
│   ├── appliances.py / hvac.py / plumbing.py / electrical.py
│   ├── exterior.py / vehicle.py / garden.py / other.py
│   └── plants_trees.py    species-specific care data (21KB)
├── tools/
│   ├── db.py              CRUD tool implementations (provider-agnostic)
│   ├── mcp_server.py      MCP server + OpenAI tool schemas + dispatcher
│   └── stdio_server.py    stdio MCP server for claude_cli provider path
├── components/            Streamlit tab components
├── knowledge/
│   ├── rag/indexer.py     RAG indexer for plant care + asset checklists
│   ├── prompts/library.yaml  reusable prompt templates
│   └── policies/maintenance_policies.yaml
├── eval/                  benchmark runner + per-agent scenario files
├── scripts/
│   └── send_monthly_reminder.py   cron-compatible Telegram digest trigger
├── agent/                 backward-compat shims (runner.py, context.py)
├── workflows/             backward-compat shims → agents/*/workflows/
├── skills/                backward-compat shims → agents/*/workflows/
├── app.py                 Streamlit entry point
└── db_init.py             schema bootstrap + admin seed (runs on first launch)
```
