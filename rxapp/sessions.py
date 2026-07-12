"""Per-user ConversationContext store.

ConversationContext is not JSON-serializable so it cannot live inside Reflex
state vars. Instead we keep a module-level dict keyed by user_id. This works
correctly for a single-process Reflex deployment (the default dev setup).
"""

from __future__ import annotations

from core.memory.short_term import ConversationContext

_contexts: dict[str, ConversationContext] = {}


def get_context(user_id: str) -> ConversationContext:
    if user_id not in _contexts:
        _contexts[user_id] = ConversationContext()
    return _contexts[user_id]


def clear_context(user_id: str) -> None:
    _contexts.pop(user_id, None)
