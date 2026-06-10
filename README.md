# Home Asset Agent

A conversational AI agent for home maintenance scheduling. Track your appliances, HVAC, plumbing, and other home assets — then ask plain-language questions about warranties, service history, and upcoming maintenance.

Built as both a functional personal tool and a portfolio demonstration of **agentic tool use**, **multi-step reasoning**, and **context management** with the Anthropic Claude API via OpenRouter.

---

## Demo

```
You:   What maintenance is coming up this month?
Agent: I'll check upcoming tasks for the next 30 days.
       [calls get_upcoming_maintenance]
       You have 3 tasks due soon:
       - HVAC filter replacement — due 2025-06-01 (overdue)
       - Dishwasher descale — due 2025-06-15 (3 days)
       - Washing machine drum clean — due 2025-07-10 (28 days)

You:   Log that I replaced the HVAC filters today, cost $35, next due in 90 days.
Agent: [calls search_assets] [calls log_maintenance]
       Done. Logged "Filter replacement" for HVAC System (cost: $35.00).
       Next service due: 2025-09-08.
```

---

## Architecture

```
Streamlit UI
      │
      ▼
agent/runner.py          LLM agentic loop (OpenRouter → Claude Sonnet)
      │
      ├── agent/context.py     ConversationContext: sliding window + summarisation
      │
      ├── tools/db.py          7 function tools over SQLite
      │       │
      │       └── data/home_assets.db    assets + maintenance_tasks tables
      │
      └── eval/                15-scenario benchmark suite (simple / moderate / complex)
```

### Key components

| File | Purpose |
|---|---|
| `agent/runner.py` | OpenAI-compatible agentic loop — sends tool results back until `finish_reason == "stop"` |
| `agent/context.py` | `ConversationContext` — sliding window history, mid-conversation summarisation, working memory |
| `tools/db.py` | 7 typed tool functions; `@tool` decorator auto-generates OpenAI function schemas from docstrings |
| `eval/run_eval.py` | Benchmark runner: tool accuracy, latency, token usage across 3 complexity tiers |

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Claude Sonnet (via OpenRouter) |
| Agent framework | OpenAI Python SDK (OpenRouter-compatible) |
| Database | SQLite |
| Data validation | Pydantic v2 |
| UI | Streamlit |
| Dependency management | uv |

---

## What it demonstrates

**Multi-step reasoning** — complex queries trigger sequential tool calls before the agent synthesises an answer. The UI shows each step as a collapsible card so the reasoning chain is visible:

- Simple (1 tool): "When does my dishwasher warranty expire?" → `search_assets`
- Moderate (2–3 tools): "Is my HVAC overdue?" → `list_assets` → `get_asset_history` → compare dates
- Complex (4+ tools): "What's my total maintenance spend by category?" → `list_assets` → `get_asset_history` × N → aggregate

**Context management** — `ConversationContext` tracks:
- Sliding window: keeps last 10 turns in full; older turns summarised by Claude Haiku
- Working memory: asset names and IDs mentioned in the conversation are injected as a context hint, avoiding redundant lookups
- Token estimate exposed in the Performance tab

**Eval suite** — `eval/run_eval.py` runs 15 benchmark scenarios and measures tool call accuracy, keyword recall, latency, and token usage per tier. Results surface in the Performance dashboard.

---

## Agent Performance Benchmarks

Run `python eval/run_eval.py` to generate results. Target baselines:

| Tier | Tool Accuracy Target | Notes |
|---|---|---|
| Simple | ≥ 90% | Single-tool direct lookups |
| Moderate | ≥ 80% | Multi-step analysis |
| Complex | ≥ 70% | Aggregation across multiple assets |

---

## Getting Started

### Prerequisites

- Python 3.11+
- `uv` package manager
- OpenRouter API key (get one at openrouter.ai)

### Setup

```bash
git clone https://github.com/yourusername/home-asset-agent
cd home-asset-agent

uv sync

cp .env.example .env
# Add your OPENROUTER_API_KEY to .env

# Create database with seed data (10 realistic home assets)
uv run python db_init.py

# Launch the app
uv run streamlit run app.py
```

### Run the benchmark

```bash
uv run python eval/run_eval.py
```

Results are saved to `eval/results.json` and displayed in the Performance tab.

---

## Database Schema

**assets**: id, name, category, brand, model, serial, purchase\_date, purchase\_price, warranty\_expiry, location, notes

**maintenance\_tasks**: id, asset\_id, task\_name, completed\_date, cost, notes, next\_due\_date, interval\_days

Asset categories: `appliances`, `HVAC`, `plumbing`, `electrical`, `exterior`, `vehicle`, `garden`, `other`

---

## Design Decisions

**SQLite over PostgreSQL** — right-sized for a personal tool with no infrastructure overhead. The tool layer is easily swappable to PostgreSQL + psycopg2 for a multi-user deployment.

**OpenAI SDK over LangChain** — the raw agentic loop is ~50 lines and worth showing explicitly. LangChain abstracts away the tool-result injection pattern that is the core of this project.

**Tool schemas from docstrings** — the `@tool` decorator on each function generates the OpenAI function schema automatically from the function signature and docstring, keeping schema and implementation co-located.

**Proactive surfacing** — the system prompt instructs the agent to check upcoming maintenance at the end of every response, making it useful as a background assistant rather than a pure Q&A tool.

---

## Project Structure

```
home-asset-agent/
├── agent/
│   ├── context.py          ConversationContext with summarisation
│   ├── runner.py           Agentic tool-use loop
│   └── system_prompt.py    Agent persona and reasoning instructions
├── components/
│   ├── assets_tab.py       Inventory dashboard
│   ├── chat_tab.py         Chat UI with reasoning trace
│   ├── performance_tab.py  Benchmark results + session metrics
│   └── schedule_tab.py     Upcoming maintenance view
├── data/
│   └── .gitkeep
├── eval/
│   ├── run_eval.py         Benchmark runner
│   └── scenarios.json      15 test scenarios
├── tools/
│   ├── db.py               7 tool functions + auto-schema decorator
│   └── schema.py           Pydantic models
├── app.py                  Streamlit entry point
└── db_init.py              Schema creation + seed data
```
