<!-- reflex managed begin (do not edit inside this block; add custom content outside the markers) -->
# Agents

This project uses the **Reflex agent skills** � up-to-date knowledge for building full-stack Python web apps with [Reflex](https://reflex.dev). Install them first, then use them as described below.

## Installing the Skills

Before working on this project, make sure the Reflex skills are available to you.

### Claude Code

If the skills are not already available, install them yourself by running these shell commands:

```bash
claude plugin marketplace add reflex-dev/agent-skills
claude plugin install reflex@reflex-agent-skills
```

Newly installed plugins load on the next session. After installing, tell the user to restart the session so the skills auto-load; until then, read the skill files directly from `~/.claude/plugins/` when you need them.

### Other agents (Cursor, OpenCode, Codex, Pi)

```
npx skills add reflex-dev/agent-skills
```

Or clone https://github.com/reflex-dev/agent-skills and copy the `skills/` folders into your agent's skill directory (see the repo README for paths).

### Verifying

Before writing or editing any Reflex code, confirm these three skills are available: `reflex-docs`, `setup-python-env`, and `reflex-process-management`. If they are not, STOP and run the install step above � do not proceed without them.

## Using the Skills

### Reflex documentation

For anything about Reflex APIs � components, state management, events, styling, database, routing, authentication � use the **reflex-docs** skill rather than relying on memory. It carries current, version-accurate docs.

### Initializing a new Reflex project

When starting a new Reflex project or setting up a development environment, you **must** follow the **setup-python-env** skill before doing anything else.

Do not skip any steps. Do not assume a virtual environment or Reflex is already available � always verify first by following the skill's instructions in order.

After the environment is ready and Reflex is installed, run:

```bash
reflex init
```

Then proceed with the user's request.

### Managing a Reflex process

When you need to compile, run, reload, or debug a Reflex application, follow the **reflex-process-management** skill for the correct sequence and error investigation steps.
<!-- reflex managed end -->

---

## AI architecture (post-LangGraph migration)

Runtime entry point: `agent/runner.py::run_turn_in_loop` (async) — used by [rxapp/state.py](rxapp/state.py). It routes on `LLM_PROVIDER`:

| Provider | Runtime | Auth | Notes |
|---|---|---|---|
| `claude_cli` | Claude Code CLI subprocess ([agent/cli_runner.py](agent/cli_runner.py)) + MCP stdio server ([tools/stdio_server.py](tools/stdio_server.py)) | OAuth via `claude auth login` — no API key needed | Bypasses LangGraph; uses EventBus + `__approval_confirmed__` sentinel for HITL |
| `claude_sdk` | LangGraph specialists via `ChatAnthropic` | `ANTHROPIC_API_KEY` | Full LangGraph flow |
| `openrouter` | LangGraph specialists via `ChatOpenAI` (OpenRouter base URL) | `OPENROUTER_API_KEY` | Full LangGraph flow; `LLM_MODEL_FAST`/`LLM_MODEL_SMART` set model per tier |

### LangGraph flow (openrouter / claude_sdk)

Every turn passes through:

```
run_turn_in_loop → dispatch_turn (LangSmith root span)
                     ├─ classify_intent (Haiku — routing.py)
                     └─ _run_specialist_events(agent, ...)  ← parallel per route
                          └─ run_graph_turn(GRAPH)
                               ├─ enter (bind correlation IDs; per-(user,agent) rate-limit gate
                               │         — throttled turns short-circuit to exit, zero LLM cost)
                               ├─ guardrail_in (layered injection scan: regex, then an LLM
                               │                classifier if the regex is clean — blocked
                               │                turns short-circuit to exit)
                               ├─ retrieve (no-op unless agent.yaml:retrieve_semantic; else
                               │            pgvector similarity search + citation injection into
                               │            the system prompt — hits are themselves injection-
                               │            scanned before being stored)
                               ├─ llm (ChatAnthropic/ChatOpenAI, tenacity retry, budget cap)
                               ├─ tools (17 shared @tool wrappers → tools/db.py, +2 insights-only:
                               │         deep_research_analysis, generate_shareable_report)
                               ├─ guardrail_tool_output (scans tool results for indirect
                               │                         injection — e.g. a crafted asset note —
                               │                         neutralizing a hit, not failing the turn)
                               ├─ handle_approval (asset only — interrupt() pause)
                               ├─ guardrail_out (PII sanitize + max length)
                               └─ exit (record_turn metric, clear correlation)
```

Specialists share [agents/_specialist.py](agents/_specialist.py) (the `SpecialistGraph` builder). Per-agent config lives in each `agents/*/agent.yaml`, including the newer `retrieve_semantic`, `rate_limit_per_min`/`rate_limit_burst`, and `guardrails.injection_classifier` knobs.

### Key module map

- **State**: `agents/state.py` (AgentState TypedDict — now also carries `user_role` alongside `user_id`, both via `core/session.py` ContextVars, never an LLM tool argument)
- **Checkpointer factory**: `core/checkpointer.py` (memory / sqlite / postgres)
- **LLM factory**: `core/llm.py`
- **Tool schemas**: `tools/schemas.py` (single source; imported by both `tools/langchain_tools.py` and `tools/stdio_server.py`)
- **Tools**: `tools/langchain_tools.py` (`@tool` wrappers over `tools/db.py`); adds `recall_knowledge`, `remember_fact`, `recall_facts` for memory. `delete_asset` is `@require_role`-gated (`core/authz.py`)
- **Insights-only tools**: `agents/insights/deep_research.py` (Deep Agents research sub-agent) and `agents/insights/report_agent.py` (PydanticAI structured report) — both run as ordinary tool calls behind the standard security perimeter, not graph replacements; see [ADR 0001](docs/architecture-decisions/0001-orchestration-framework-choice.md)
- **Adapter**: `agent/langgraph_adapter.py` (graph output → UI event dicts; also handles `resume_graph_turn` for interrupt Confirm/Cancel)
- **Dispatcher**: `agents/orchestrator/dispatcher.py` (classify + parallel fan-out + merge, wrapped in a `@traceable` LangSmith span)
- **RAG**: `core/memory/semantic.py` (pgvector-backed store/retrieve), `knowledge/rag/chunker.py` (LlamaIndex `SentenceSplitter`), `knowledge/rag/ingest.py` (chunk + store long-form docs with citation metadata)
- **Security**: `core/guardrails.py` (layered injection defense + PII), `core/injection_classifier.py` (LLM classifier layer), `core/rate_limit.py` (token bucket), `core/authz.py` (tool-level role gating)

### Observability

- Structured logs: `core/logging.py` (structlog JSON + correlation ID contextvars + PII redaction). `llm_finished` carries `prompt_version` (parsed from the active specialist's system-prompt front-matter).
- Metrics: `core/metrics.py` (Prometheus counters/histograms + in-memory ring buffer for the admin UI)
- Audit trail: `core/audit.py` (Pydantic-validated JSONL, **tamper-evident hash chain** — `verify_chain()` / `scripts/verify_audit_log.py` detect the first broken link — weekly gzip rotation with chain continuity preserved via a sidecar state file). Legacy shim at `core/observability.py::audit_log` for pre-migration callers. `data/audit.log` is gitignored (runtime data, not source).
- Alerts: `core/alerts.py` (Discord/Slack webhook)
- Tracing: LangSmith (`LANGCHAIN_TRACING_V2=true`) or self-hosted Langfuse (`infra/langfuse-compose.yaml`)

### Evaluation & CI

- `eval/run_eval.py` runs `eval/scenarios.json` (19 scenarios, incl. 4 RAG-specific) against the real stack, scoring mechanically (pass/fail gate) and via `eval/judge.py` (LLM-as-judge groundedness/relevance, additive signal only). `eval/compare.py` diffs against the last committed `eval/results.json` baseline.
- `.github/workflows/ci.yml` — offline test suite + gitleaks secrets scan + prompt-version-bump check, on every PR.
- `.github/workflows/eval-nightly.yml` — the real-API eval above, nightly/manual only (keeps cost off every push).

### Env vars

Minimum viable `.env`:

```
LLM_PROVIDER=openrouter                    # or claude_sdk, claude_cli
OPENROUTER_API_KEY=sk-or-v1-...            # or ANTHROPIC_API_KEY for claude_sdk
LLM_MODEL_FAST=anthropic/claude-haiku-4-5   # optional override
LLM_MODEL_SMART=anthropic/claude-sonnet-4-6 # optional override
CHECKPOINTER=sqlite                        # memory | sqlite | postgres
LANGCHAIN_TRACING_V2=true                  # optional
LANGCHAIN_API_KEY=lsv2_...                 # optional
LANGCHAIN_PROJECT=home-asset-agent-dev     # optional
VOYAGE_API_KEY=pa-...                      # recommended (real RAG embeddings);
                                            # without it, retrieval degrades to a
                                            # loudly-logged hash stub, not silently
```

See `infra/env.langgraph.example` for the full annotated list. Per-agent (not env) knobs — `retrieve_semantic`, `rate_limit_per_min`/`rate_limit_burst`, `guardrails.*` — live in each `agents/*/agent.yaml`; see the README's "Per-agent knobs" table.

Both `DATABASE_URL`/Supabase connections need the `pgvector` Postgres extension for `semantic_memory.embedding_vec` — `ensure_schema()` runs `CREATE EXTENSION IF NOT EXISTS vector` for you, but the DB role needs privileges to do so.
