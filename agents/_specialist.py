"""Shared LangGraph specialist builder.

Every specialist (asset, maintenance, insights) compiles the same shape:

    START -> enter -> guardrail_in -> retrieve -> llm <-> tools -> guardrail_tool_output -> guardrail_out -> exit
                (rate-limit gate)  (injection scan)  (auto-RAG +           \\-> handle_approval (asset only) /
                                                       inline scan)

`enter` short-circuits straight to `exit` on a rate-limit throttle;
`guardrail_in` short-circuits to `exit` on a blocked injection. `retrieve` is
a no-op (zero embedding/LLM cost) for agents with `retrieve_semantic: false`
in their agent.yaml. `guardrail_tool_output` scans tool results for indirect
injection (e.g. a crafted asset note) before they can reach another `llm`
call; retrieved-context injection scanning happens inside `retrieve` itself,
*before* it's ever placed in front of an LLM — scanning it downstream of
`tools` would miss the first `llm` call each turn.

Instance-based rather than free-function so each node closes over `self.spec`
(agent config, tools, guardrails, system prompt) without threading it through
every signature.

Per-specialist customisations live in `agents/<name>/graph.py` — asset supplies
its own `handle_approval` node via `SpecialistGraph.set_approval_handler`; the
others don't call `set_approval_handler` and skip the branch entirely.
"""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from agents.state import AgentState
from core.audit import audit
from core.authz import AuthorizationError
from core.checkpointer import get_checkpointer
from core.guardrails import Guardrails
from core.llm import MissingCredentialsError, UnsupportedProviderError, build_chat_model
from core.logging import bind_correlation, clear_correlation, get_logger
from core.metrics import TurnSummary, emit_budget_breach, emit_guardrail_block, record_turn
from core.models import get_provider, resolve_model
from core.pricing import estimate_cost_usd
from core.rate_limit import check_rate_limit
from core.registry import AgentRegistry
from core.session import set_current_user, set_current_user_role

log = get_logger(__name__)

# Sentinel messages the app sends when the user confirms/cancels an approval
# card. Kept out of the injection guard — they're internal control strings.
INTERNAL_SENTINELS = frozenset({"__approval_confirmed__", "__approval_cancelled__"})

# Tools that mutate persistent state; asset_index absorbs their results.
_ASSET_TRACKING_TOOLS = frozenset({"list_assets", "search_assets", "get_asset_history", "add_asset"})

# Tools whose results contain free text a user could have crafted (asset
# names/notes) — scanned for indirect prompt injection after every tool call.
_EXTERNAL_CONTENT_TOOLS = frozenset({"list_assets", "search_assets", "get_asset_history"})


def _is_retryable(exc: BaseException) -> bool:
    """Retry transient network hiccups; fail fast on config + upstream rate limits.

    Rate limits are already retried once by the provider SDK's internal
    backoff — retrying at this layer just multiplies the delay before the
    error surfaces to the user (the underlying model is unavailable).
    """
    if isinstance(exc, (MissingCredentialsError, UnsupportedProviderError)):
        return False
    # Provider SDK rate-limit / auth / bad-request errors — no point retrying.
    from anthropic import APIStatusError as _AnthropicStatus
    from openai import APIStatusError as _OpenAIStatus
    if isinstance(exc, (_AnthropicStatus, _OpenAIStatus)):
        status = getattr(exc, "status_code", None)
        if status in (401, 403, 429):
            return False
    return isinstance(exc, Exception)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception(_is_retryable),
)
def _invoke_llm(llm: Any, messages: list[BaseMessage]) -> AIMessage:
    """Shared LLM call with tenacity retry (3 attempts, 1-8s exp backoff)."""
    return llm.invoke(messages)


class SpecialistGraph:
    """Builds and holds a compiled LangGraph specialist subgraph."""

    def __init__(
        self,
        agent_name: str,
        *,
        tools: list[BaseTool],
        tier: str = "sonnet",
    ) -> None:
        self.agent_name = agent_name
        self.tools = tools
        self.tier = tier
        self.config = AgentRegistry().get(agent_name)
        self.guardrails = Guardrails(self.config.guardrails)
        self.system_prompt = _load_system_prompt(agent_name)
        self._prompt_version = _load_prompt_version(agent_name)
        # This LangGraph version's default handle_tool_errors only catches its
        # own ToolInvocationError and re-raises everything else — so a role
        # denial must be explicitly listed here to come back as an error
        # ToolMessage (fed to the LLM) instead of crashing the turn.
        self._tool_node = ToolNode(tools, handle_tool_errors=AuthorizationError)
        self._approval_handler: Callable[[AgentState, RunnableConfig], dict] | None = None
        self._approval_router: Callable[[AgentState], str] | None = None

    def set_approval_handler(
        self,
        handler: Callable[[AgentState, RunnableConfig], dict],
        router: Callable[[AgentState], str],
    ) -> None:
        """Wire the interrupt-based approval branch. Called by asset only.

        `router` should return "handle_approval" when the last ToolMessage
        needs human review, else "llm". `handler` is the node body.
        """
        self._approval_handler = handler
        self._approval_router = router

    # ── Nodes ─────────────────────────────────────────────────────────

    def enter_node(self, state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        metadata = config.get("metadata", {}) or {}
        bind_correlation(
            request_id=state.get("request_id") or metadata.get("request_id"),
            user_id=state.get("user_id") or metadata.get("user_id"),
            agent=self.agent_name,
        )
        if user_id := state.get("user_id"):
            set_current_user(user_id)
        set_current_user_role(state.get("user_role", ""))
        log.info("graph_enter", agent=self.agent_name, messages=len(state.get("messages", [])))

        base: dict[str, Any] = {
            "active_specialist": self.agent_name,
            "iteration": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "usd_cost": 0.0,
            "termination_reason": None,
            "retrieved_context": [],
        }
        allowed, retry_after = check_rate_limit(
            self.agent_name,
            state.get("user_id", ""),
            capacity=self.config.rate_limit_burst,
            refill_per_min=self.config.rate_limit_per_min,
        )
        if not allowed:
            log.warning("rate_limited", agent=self.agent_name, user_id=state.get("user_id", ""), retry_after_s=retry_after)
            emit_budget_breach(self.agent_name, "rate_limited")
            audit(
                "rate_limit_exceeded",
                request_id=state.get("request_id", ""),
                actor="system",
                user_id=state.get("user_id"),
                agent=self.agent_name,
                payload={"retry_after_s": round(retry_after, 2)},
            )
            return {
                **base,
                "termination_reason": "rate_limited",
                "messages": [AIMessage(
                    content=f"You're sending requests too quickly. Try again in {int(retry_after) + 1}s."
                )],
            }
        return base

    def guardrail_in_node(self, state: AgentState) -> dict[str, Any]:
        messages = state.get("messages", [])
        last_user = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
        if last_user is None:
            return {}
        text = last_user.content if isinstance(last_user.content, str) else ""
        if text in INTERNAL_SENTINELS:
            return {}
        verdict = self.guardrails.scan(text, source="user_message")
        if verdict.blocked:
            emit_guardrail_block(f"injection_{verdict.layer}")
            log.warning(
                "guardrail_injection_blocked", agent=self.agent_name, layer=verdict.layer,
                category=verdict.category, preview=text[:80],
            )
            audit(
                "guardrail_injection_blocked",
                request_id=state.get("request_id", ""),
                actor="system",
                user_id=state.get("user_id"),
                agent=self.agent_name,
                payload={"layer": verdict.layer, "category": verdict.category},
            )
            return {
                "messages": [AIMessage(content="I cannot process that request.")],
                "termination_reason": "guardrail",
            }
        return {}

    def retrieve_node(self, state: AgentState) -> dict[str, Any]:
        """Auto-retrieval for agents with `retrieve_semantic: true`. No-op
        (zero embedding/LLM cost) otherwise. Hits are injection-scanned here,
        before storage, since this is upstream of every `llm` call this turn —
        scanning downstream of `tools` would miss the first one."""
        if not self.config.retrieve_semantic:
            return {}
        messages = state.get("messages", [])
        last_user = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
        if last_user is None or not isinstance(last_user.content, str):
            return {}

        from core.memory.semantic import SemanticMemory

        try:
            hits = SemanticMemory(self.agent_name).retrieve(last_user.content, top_k=3)
        except Exception:
            log.exception("auto_retrieve_failed", agent=self.agent_name)
            return {}

        safe_hits: list[dict[str, Any]] = []
        for hit in hits:
            verdict = self.guardrails.scan(hit.get("content", ""), source="retrieved_context")
            if verdict.blocked:
                emit_guardrail_block(f"retrieved_context_{verdict.layer}")
                log.warning(
                    "guardrail_retrieved_context_blocked", agent=self.agent_name,
                    layer=verdict.layer, category=verdict.category, hit_id=hit.get("id"),
                )
                audit(
                    "guardrail_injection_blocked",
                    request_id=state.get("request_id", ""),
                    actor="system",
                    user_id=state.get("user_id"),
                    agent=self.agent_name,
                    payload={"layer": verdict.layer, "category": verdict.category, "source": "retrieved_context"},
                )
                continue
            safe_hits.append(hit)
        return {"retrieved_context": safe_hits}

    def llm_node(self, state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        iteration = int(state.get("iteration", 0)) + 1
        usd_so_far = float(state.get("usd_cost", 0.0))

        if iteration > self.config.max_turns:
            log.warning("max_iter_reached", agent=self.agent_name, iteration=iteration, cap=self.config.max_turns)
            emit_budget_breach(self.agent_name, "max_iter")
            return {
                "iteration": iteration,
                "termination_reason": "max_iter",
                "messages": [AIMessage(content="I've reached my step limit for this turn. Please try again with a narrower request.")],
            }
        if self.config.budget_usd is not None and usd_so_far >= self.config.budget_usd:
            log.warning("budget_reached", agent=self.agent_name, usd_so_far=usd_so_far, cap=self.config.budget_usd)
            emit_budget_breach(self.agent_name, "usd")
            return {
                "iteration": iteration,
                "termination_reason": "budget",
                "messages": [AIMessage(content="I've reached the cost budget for this turn. Please try again.")],
            }

        llm = build_chat_model(tier=self.tier, temperature=0.0, max_tokens=4096, timeout_s=30.0).bind_tools(self.tools)

        system_prompt = self.system_prompt
        if hint := _working_memory_hint(state.get("asset_index", {})):
            system_prompt = system_prompt + hint
        if ctx := _retrieved_context_block(state.get("retrieved_context", [])):
            system_prompt = system_prompt + ctx

        messages_in: list[BaseMessage] = [SystemMessage(content=system_prompt), *state.get("messages", [])]

        t0 = time.monotonic()
        resp: AIMessage = _invoke_llm(llm, messages_in)
        duration_ms = int((time.monotonic() - t0) * 1000)

        usage = getattr(resp, "usage_metadata", None) or {}
        in_tok = int(usage.get("input_tokens", 0))
        out_tok = int(usage.get("output_tokens", 0))
        model_name = resolve_model(self.tier)
        delta_usd = estimate_cost_usd(model_name, in_tok, out_tok)

        log.info(
            "llm_finished",
            agent=self.agent_name,
            prompt_version=self._prompt_version,
            iteration=iteration,
            duration_ms=duration_ms,
            tokens_in=in_tok,
            tokens_out=out_tok,
            delta_usd=round(delta_usd, 6),
            tool_calls=len(getattr(resp, "tool_calls", []) or []),
        )
        return {
            "messages": [resp],
            "iteration": iteration,
            "tokens_in": int(state.get("tokens_in", 0)) + in_tok,
            "tokens_out": int(state.get("tokens_out", 0)) + out_tok,
            "usd_cost": usd_so_far + delta_usd,
        }

    def tools_node(self, state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        result = self._tool_node.invoke(state)
        tool_messages: list[ToolMessage] = result.get("messages", [])
        updated_index = dict(state.get("asset_index", {}))
        for tm in tool_messages:
            _absorb_asset_ids(tm, updated_index)
        return {
            "messages": tool_messages,
            "asset_index": _cap_index(updated_index),
        }

    def guardrail_tool_output_node(self, state: AgentState) -> dict[str, Any]:
        """Indirect-injection catch: scans tool results that could carry
        user-crafted free text (e.g. asset notes) before they can reach
        another `llm` call. On a hit, the message content is replaced with a
        neutral marker rather than terminating the turn — one poisoned
        result shouldn't kill an otherwise-legitimate multi-tool turn."""
        messages = state.get("messages", [])
        new_messages: list[BaseMessage] = []
        changed = False
        for m in messages:
            if not (isinstance(m, ToolMessage) and m.name in _EXTERNAL_CONTENT_TOOLS):
                continue
            content = m.content if isinstance(m.content, str) else str(m.content)
            verdict = self.guardrails.scan(content, source="tool_output")
            if not verdict.blocked:
                continue
            changed = True
            emit_guardrail_block(f"tool_output_{verdict.layer}")
            log.warning(
                "guardrail_tool_output_blocked", agent=self.agent_name, tool=m.name,
                layer=verdict.layer, category=verdict.category,
            )
            audit(
                "guardrail_injection_blocked",
                request_id=state.get("request_id", ""),
                actor="system",
                user_id=state.get("user_id"),
                agent=self.agent_name,
                payload={"layer": verdict.layer, "category": verdict.category, "source": "tool_output", "tool": m.name},
            )
            new_messages.append(ToolMessage(
                content="[content omitted: potential prompt injection detected]",
                tool_call_id=m.tool_call_id, name=m.name, id=m.id,
            ))
        if not changed:
            return {}
        # add_messages reducer matches on id, so returning these replaces the
        # originals in state rather than appending duplicates.
        return {"messages": new_messages}

    def guardrail_out_node(self, state: AgentState) -> dict[str, Any]:
        messages = state.get("messages", [])
        last = messages[-1] if messages else None
        if not isinstance(last, AIMessage):
            return {}
        content = last.content if isinstance(last.content, str) else str(last.content)
        sanitized = self.guardrails.sanitize_output(content)
        if sanitized == content:
            return {}
        return {"messages": [AIMessage(content=sanitized, id=last.id)]}

    def exit_node(self, state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        outcome = state.get("termination_reason") or "ok"
        record_turn(TurnSummary(
            ts=time.time(),
            request_id=state.get("request_id", ""),
            user_id=state.get("user_id", ""),
            agent=self.agent_name,
            provider=get_provider().value,
            outcome=outcome,
            duration_s=0.0,
            cost_usd=float(state.get("usd_cost", 0.0)),
            tool_calls=_count_tool_calls(state.get("messages", [])),
            tokens_in=int(state.get("tokens_in", 0)),
            tokens_out=int(state.get("tokens_out", 0)),
            termination_reason=state.get("termination_reason"),
        ))
        log.info(
            "graph_exit",
            agent=self.agent_name,
            outcome=outcome,
            usd_cost=round(float(state.get("usd_cost", 0.0)), 6),
            iteration=state.get("iteration", 0),
        )
        clear_correlation()
        return {}

    # ── Edge routers ──────────────────────────────────────────────────

    def _route_after_enter(self, state: AgentState) -> str:
        return "exit" if state.get("termination_reason") == "rate_limited" else "guardrail_in"

    def _route_after_guardrail_in(self, state: AgentState) -> str:
        return "exit" if state.get("termination_reason") == "guardrail" else "retrieve"

    def _route_after_llm(self, state: AgentState) -> str:
        if state.get("termination_reason") in ("max_iter", "budget"):
            return "guardrail_out"
        messages = state.get("messages", [])
        last = messages[-1] if messages else None
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tools"
        return "guardrail_out"

    def _route_after_tools(self, state: AgentState) -> str:
        if self._approval_router is not None:
            return self._approval_router(state)
        return "llm"

    # ── Assembler ─────────────────────────────────────────────────────

    def build(self, checkpointer: Any = None) -> Any:
        """Compile the graph. Uses the process-wide checkpointer unless overridden."""
        if checkpointer is None:
            checkpointer = get_checkpointer()

        graph = StateGraph(AgentState)
        graph.add_node("enter", self.enter_node)
        graph.add_node("guardrail_in", self.guardrail_in_node)
        graph.add_node("retrieve", self.retrieve_node)
        graph.add_node("llm", self.llm_node)
        graph.add_node("tools", self.tools_node)
        graph.add_node("guardrail_tool_output", self.guardrail_tool_output_node)
        graph.add_node("guardrail_out", self.guardrail_out_node)
        graph.add_node("exit", self.exit_node)

        graph.add_edge(START, "enter")
        graph.add_conditional_edges(
            "enter", self._route_after_enter, {"guardrail_in": "guardrail_in", "exit": "exit"},
        )
        graph.add_conditional_edges(
            "guardrail_in", self._route_after_guardrail_in, {"retrieve": "retrieve", "exit": "exit"},
        )
        graph.add_edge("retrieve", "llm")
        graph.add_conditional_edges(
            "llm", self._route_after_llm, {"tools": "tools", "guardrail_out": "guardrail_out"},
        )

        after_tools_map: dict[str, str] = {"llm": "llm"}
        if self._approval_handler is not None:
            graph.add_node("handle_approval", self._approval_handler)
            graph.add_edge("handle_approval", "guardrail_out")
            after_tools_map["handle_approval"] = "handle_approval"

        graph.add_edge("tools", "guardrail_tool_output")
        graph.add_conditional_edges("guardrail_tool_output", self._route_after_tools, after_tools_map)
        graph.add_edge("guardrail_out", "exit")
        graph.add_edge("exit", END)

        return graph.compile(checkpointer=checkpointer)


# ── Helpers ──────────────────────────────────────────────────────────

def _split_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    """Split a leading `---\\n...\\n---\\n` YAML block (if present) from the
    body. Front-matter is for humans/tooling (version tracking) — it's never
    sent to the LLM."""
    if not raw.startswith("---\n"):
        return {}, raw
    end = raw.find("\n---\n", 4)
    if end == -1:
        return {}, raw
    import yaml
    meta = yaml.safe_load(raw[4:end]) or {}
    body = raw[end + 5:]
    return (meta if isinstance(meta, dict) else {}), body


def _load_system_prompt(agent_name: str) -> str:
    _, body = _split_front_matter(_read_prompt_file(agent_name))
    return body.replace("{today}", date.today().isoformat())


def _load_prompt_version(agent_name: str) -> int:
    """Parse the front-matter `version:` field for logging/audit correlation."""
    meta, _ = _split_front_matter(_read_prompt_file(agent_name))
    try:
        return int(meta.get("version", 0))
    except (TypeError, ValueError):
        return 0


def _read_prompt_file(agent_name: str) -> str:
    prompt_path = Path(__file__).parent / agent_name / "prompts" / "system.md"
    return prompt_path.read_text(encoding="utf-8")


def _working_memory_hint(index: dict[str, int]) -> str:
    if not index:
        return ""
    items = ", ".join(f"{n} (id={i})" for n, i in list(index.items())[-8:])
    return f"\n\n[Assets referenced this session: {items}]"


def _retrieved_context_block(hits: list[dict[str, Any]]) -> str:
    if not hits:
        return ""
    lines = [
        f"- [{h.get('metadata', {}).get('source', 'knowledge')}#{h.get('id')}] "
        f"{h.get('content', '')} (relevance={h.get('score')})"
        for h in hits
    ]
    return (
        "\n\n[Retrieved reference context — cite the bracketed source tag "
        "like [checklist#12] if you use this in your answer, and do not "
        "state it as fact if it doesn't actually apply to the user's question]\n"
        + "\n".join(lines)
    )


def _absorb_asset_ids(tm: ToolMessage, index: dict[str, int]) -> None:
    if tm.name not in _ASSET_TRACKING_TOOLS:
        return
    content = tm.content
    try:
        data = json.loads(content) if isinstance(content, str) else content
    except (json.JSONDecodeError, TypeError):
        return
    if not isinstance(data, dict):
        return
    if tm.name in ("list_assets", "search_assets"):
        for asset in data.get("assets", []) or []:
            if isinstance(asset, dict):
                _put(index, asset.get("name", ""), asset.get("id", 0))
    elif tm.name == "get_asset_history":
        asset = data.get("asset") or {}
        if isinstance(asset, dict):
            _put(index, asset.get("name", ""), asset.get("id", 0))
    elif tm.name == "add_asset":
        if data.get("status") == "created":
            _put(index, data.get("name", ""), data.get("asset_id", 0))


def _put(index: dict[str, int], name: str, id_: Any) -> None:
    if isinstance(name, str) and name and isinstance(id_, int) and id_:
        index[name.lower()] = id_


def _cap_index(index: dict[str, int], limit: int = 8) -> dict[str, int]:
    if len(index) <= limit:
        return index
    return dict(list(index.items())[-limit:])


def _count_tool_calls(messages: list[BaseMessage]) -> int:
    return sum(1 for m in messages if isinstance(m, ToolMessage))
