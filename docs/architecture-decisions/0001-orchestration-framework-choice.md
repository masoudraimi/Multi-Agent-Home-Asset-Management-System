# 0001 — Orchestration framework choice

## Status
Accepted (2026-08-31)

## Context
This app is a multi-agent home-asset-management assistant: an orchestrator
classifies intent and fans out to specialist agents (asset, maintenance,
insights), each running a tool-calling loop over a shared Postgres backend,
with human-in-the-loop approval for destructive actions, checkpointed state,
structured guardrails, and an audit trail. Several agentic-orchestration
frameworks could plausibly serve as the backbone: LangChain/LangGraph,
LlamaIndex, PydanticAI, Semantic Kernel, and LangChain's newer Deep Agents
library. This ADR records why LangGraph remains the primary orchestrator,
and where the other frameworks earned a real, contained role instead of
being forced in for their own sake.

## Decision

**LangGraph/LangChain is the primary orchestrator** (`agents/_specialist.py`,
`agents/orchestrator/dispatcher.py`). It's the right fit here because the
app's actual requirements are exactly what LangGraph is built for:
durable, checkpointed state across turns (`core/checkpointer.py`); an
explicit graph shape that can express governance nodes as first-class
citizens (`enter` rate-limit gate, `guardrail_in`/`guardrail_tool_output`
injection scanning, `retrieve` auto-RAG, `guardrail_out` PII sanitization —
see `agents/_specialist.py`'s module docstring for the full node sequence);
and native `interrupt()`-based human-in-the-loop for the asset delete-
approval flow (`agents/asset/graph.py`). These aren't incidental features —
they're the load-bearing parts of this app's security and reliability
posture, and LangGraph lets them live as inspectable graph nodes rather
than scattered middleware hooks.

**LlamaIndex** earned a narrow, real role: `knowledge/rag/chunker.py` uses
its `SentenceSplitter` (importable standalone, no full LlamaIndex
application needed) for sentence-aware chunk boundaries when ingesting
long-form reference text. LlamaIndex's query-engine/index abstractions
weren't adopted — the app's retrieval need (pgvector similarity search
scoped by agent) is already well served by `core/memory/semantic.py`
without a second indexing framework layered on top.

**LangChain's Deep Agents** (`agents/insights/deep_research.py`) is used
for genuinely open-ended, multi-step research questions the insights
specialist gets — e.g. "why is my utility bill high," which benefits from
its own planning loop rather than one flat tool-calling pass. A
compatibility spike (see that module's docstring) confirmed
`create_deep_agent`'s compiled graph accepts this app's existing `@tool`
wrappers and `BaseChatModel` instances directly, and its `DeepAgentState`
TypedDict can be extended with extra fields without breaking compilation —
so the state shape is genuinely compatible. What isn't compatible out of
the box is the *governance* surface: deep agents' own graph topology
(`model <-> tools` plus built-in planning/filesystem middleware) has none
of `SpecialistGraph`'s rate-limiting, layered injection defense, RAG
auto-retrieve, or audit nodes. Reimplementing those as deepagents
middleware would be a materially larger, separate effort. Rather than
replace `agents/insights`'s graph wholesale and lose that perimeter, the
deep agent runs *behind* it, as an ordinary tool call — its result still
passes through `guardrail_tool_output` like any other tool result before
reaching the LLM or the user.

**PydanticAI** (`agents/insights/report_agent.py`) is used for one
contained structured-extraction step: turning free-text analysis notes into
a validated `HomeInsightsReport`. This is deliberately narrow — it talks to
Anthropic directly rather than going through `core/llm.py`'s
provider-switching abstraction, which is a fine tradeoff for a single,
clearly-scoped tool but wouldn't be if PydanticAI were adopted more
broadly. It sits alongside LangChain's own `.with_structured_output()`
(already used elsewhere in the codebase) rather than replacing it —
PydanticAI is the framework purpose-built for this exact "typed output,
validated by the framework itself" job.

**Semantic Kernel was evaluated and not adopted.** It's a strong framework
for .NET-first teams and for orgs standardizing on Microsoft's AI stack
(Azure OpenAI integration, enterprise plugin model), but its Python SDK is
the secondary surface behind the C#/.NET implementation, with a smaller
community and slower feature parity for the agentic patterns this app
needs (durable checkpointed graphs, native human-in-the-loop interrupts).
Adopting it here would mean either running a second orchestration runtime
alongside LangGraph for no functional gain, or replacing LangGraph
entirely and rebuilding the checkpointing/interrupt/governance-node
architecture this app already has working — neither is justified when
nothing about this app's requirements points at Semantic Kernel's actual
strengths (enterprise .NET integration, Microsoft-ecosystem plugins).
Knowing what *not* to force into an architecture is as much a framework
decision as picking one to use.

## Consequences
- One primary orchestration engine (LangGraph) keeps the security/
  governance graph legible and testable as a single node sequence, rather
  than splitting that logic across multiple frameworks' middleware systems.
- Deep Agents and PydanticAI usage is intentionally contained to specific
  tools, not graph-level replacements — this keeps the security perimeter
  intact but means their own advanced features (deep agents' filesystem
  scratchpad, PydanticAI's dependency-injection `deps_type`) aren't
  exercised beyond what each tool actually needs.
- If a future specialist's workload genuinely outgrows a flat tool-calling
  loop's governance needs too (not just its reasoning needs), revisit
  whether deepagents middleware for rate-limiting/injection-scanning is
  worth building — the spike in `deep_research.py` would be the starting
  point.
