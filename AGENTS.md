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
                               ├─ enter (bind correlation IDs)
                               ├─ guardrail_in (injection block)
                               ├─ llm (ChatAnthropic/ChatOpenAI, tenacity retry, budget cap)
                               ├─ tools (14 @tool wrappers → tools/db.py)
                               ├─ handle_approval (asset only — interrupt() pause)
                               ├─ guardrail_out (PII sanitize + max length)
                               └─ exit (record_turn metric, clear correlation)
```

Specialists share [agents/_specialist.py](agents/_specialist.py) (the `SpecialistGraph` builder). Per-agent config lives in each `agents/*/agent.yaml`.

### Key module map

- **State**: `agents/state.py` (AgentState TypedDict)
- **Checkpointer factory**: `core/checkpointer.py` (memory / sqlite / postgres)
- **LLM factory**: `core/llm.py`
- **Tool schemas**: `tools/schemas.py` (single source; imported by both `tools/langchain_tools.py` and `tools/stdio_server.py`)
- **Tools**: `tools/langchain_tools.py` (`@tool` wrappers over `tools/db.py`); adds `recall_knowledge`, `remember_fact`, `recall_facts` for memory
- **Adapter**: `agent/langgraph_adapter.py` (graph output → UI event dicts; also handles `resume_graph_turn` for interrupt Confirm/Cancel)
- **Dispatcher**: `agents/orchestrator/dispatcher.py` (classify + parallel fan-out + merge, wrapped in a `@traceable` LangSmith span)

### Observability

- Structured logs: `core/logging.py` (structlog JSON + correlation ID contextvars + PII redaction)
- Metrics: `core/metrics.py` (Prometheus counters/histograms + in-memory ring buffer for the admin UI)
- Audit trail: `core/audit.py` (Pydantic-validated JSONL, weekly gzip rotation). Legacy shim at `core/observability.py::audit_log` for pre-migration callers.
- Alerts: `core/alerts.py` (Discord/Slack webhook)
- Tracing: LangSmith (`LANGCHAIN_TRACING_V2=true`) or self-hosted Langfuse (`infra/langfuse-compose.yaml`)

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
VOYAGE_API_KEY=pa-...                      # optional (RAG); falls back to hash stub
```

See `infra/env.langgraph.example` for the full annotated list.
