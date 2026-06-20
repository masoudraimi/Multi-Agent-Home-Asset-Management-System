# Home Asset Agent

A conversational AI agent for managing home assets and maintenance. Track appliances, HVAC, plumbing, vehicles, plants, and more — then ask plain-language questions about warranties, service history, upcoming tasks, and spend analytics.

Built as both a functional personal tool and a portfolio demonstration of **multi-agent orchestration**, **agentic tool use**, **LLM-as-judge workflows**, and **provider-agnostic design** with the Claude Agent SDK and OpenRouter.

---

## Demo

```
You:   Add my dishwasher.
Agent: [calls get_onboarding_questions]
       Let's get your dishwasher set up. What brand and model is it?

You:   Bosch Series 6, bought it in March 2023 for $1,200.
Agent: [calls review_asset_draft] → confidence: high, ready_to_save: true
       Here's the summary — does this look right?
         Name: Dishwasher, Brand: Bosch, Model: Series 6
         Purchase date: 2023-03-01, Price: $1,200

You:   Yes.
Agent: [calls add_asset]
       Saved. Also, your HVAC filter replacement is 12 days overdue.
```

---

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
  11 MCP tools over SQLite — add, list, search, update assets;
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

---

## Provider Switching

The agent loop and all LLM calls are provider-agnostic. Switch at runtime via a single env var:

```bash
LLM_PROVIDER=claude_cli    # default
LLM_PROVIDER=claude_sdk
LLM_PROVIDER=openrouter
```

| Provider | Env var required | How it works |
|---|---|---|
| `claude_sdk` | `ANTHROPIC_API_KEY` | `claude_agent_sdk.query()` — runs the `claude` binary via the Python SDK with an in-process MCP server |
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

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Claude Sonnet 4.6 / Haiku 4.5 |
| Agent framework (default) | Claude Agent SDK + in-process MCP |
| Agent framework (alternate) | OpenAI SDK → OpenRouter |
| Database | SQLite |
| Tool protocol | MCP (Model Context Protocol) |
| Data validation | Pydantic v2 |
| UI | Streamlit |
| Observability | OpenTelemetry |
| Dependency management | uv |

---

## Key Patterns Demonstrated

**Multi-agent orchestration** — the orchestrator classifies intent with a lightweight Haiku call and fans out to one or more specialist agents. Complex queries (e.g. "full home health report") dispatch to multiple agents concurrently.

**LLM-as-judge** — before saving a new asset, `review_asset_draft` calls Haiku to score completeness, flag suspicious values, and surface missing fields. The agent only calls `add_asset` after the user confirms.

**Human-in-the-loop** — `HumanApprovalRequested` events flow through the `EventBus` to render a confirmation card in the Streamlit UI before any write is committed.

**Working memory** — `ConversationContext` tracks asset names and IDs seen in tool results and injects them as a hint on subsequent turns, reducing redundant lookups.

**Provider abstraction** — `core/models.py` exposes `simple_complete()` and `resolve_model()` so callers never hard-code a provider. `BaseAgent` branches between `_run_sdk()` and `_run_openrouter()` based on `LLM_PROVIDER`.

**MCP tools** — all 11 tools are defined once in `tools/mcp_server.py` with Pydantic schemas. The same definitions generate both the in-process MCP server (Claude SDK path) and OpenAI function-calling schemas (OpenRouter path).

---

## Getting Started

### Prerequisites

- Python 3.13+
- `uv` package manager
- API key for your chosen provider:
  - Claude SDK: `ANTHROPIC_API_KEY`
  - OpenRouter: `OPENROUTER_API_KEY`

### Setup

```bash
git clone https://github.com/yourusername/home-asset-agent
cd home-asset-agent

uv sync

# Copy and fill in your env vars
cp .env.example .env
```

`.env` example:

```env
# Choose one provider
LLM_PROVIDER=claude_sdk       # or: openrouter

ANTHROPIC_API_KEY=sk-ant-...  # required for claude_sdk
OPENROUTER_API_KEY=sk-or-...  # required for openrouter

# Optional: Telegram digest
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

```bash
# Initialise the database with seed data
uv run python db_init.py

# Launch the app
uv run streamlit run app.py
```

### Run the eval suite

```bash
uv run python eval/run_eval.py
```

Benchmarks cover the orchestrator, asset agent, and maintenance agent across simple / moderate / complex scenarios. Results are saved to `eval/results/` and surfaced in the Observability tab.

---

## Database Schema

**assets**: `id`, `name`, `category`, `brand`, `model`, `serial`, `purchase_date`, `purchase_price`, `warranty_expiry`, `location`, `notes`, `plant_species`, `plant_size`, `planting_date`, `plant_notes`

**maintenance_tasks**: `id`, `asset_id`, `task_name`, `completed_date`, `cost`, `notes`, `next_due_date`, `interval_days`

Asset categories: `appliances`, `HVAC`, `plumbing`, `electrical`, `exterior`, `vehicle`, `garden`, `plants_trees`, `other`

---

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
│   ├── maintenance/
│   │   ├── agent.py / agent.yaml / prompts/system.md
│   │   └── workflows/telegram.py      push digest
│   └── insights/
│       └── agent.py / agent.yaml / prompts/system.md
├── core/
│   ├── base_agent.py      provider-aware agent loop
│   ├── models.py          Provider enum, resolve_model(), simple_complete()
│   ├── registry.py        AgentRegistry — loads agent.yaml configs
│   ├── memory/            short_term (sliding window), long_term, semantic
│   ├── guardrails.py      injection detection + output sanitisation
│   ├── event_bus.py       publish/subscribe for UI events
│   └── observability.py   OTel tracer setup
├── tools/
│   ├── db.py              SQLite tool implementations
│   └── mcp_server.py      MCP server + OpenAI tool schemas + dispatcher
├── components/            Streamlit tab components
├── data/                  asset_questions.json, plant_care.json, checklist
├── eval/                  benchmark runner + per-agent scenario files
├── knowledge/             RAG indexer, prompt library, maintenance policies
├── app.py                 Streamlit entry point
└── db_init.py             Schema creation + seed data
```
