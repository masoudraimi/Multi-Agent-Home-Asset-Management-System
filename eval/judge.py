"""LLM-as-judge scoring for groundedness and answer quality.

Additive signal alongside eval/run_eval.py's mechanical tool-hit/keyword
pass-fail check — never gates `passed`, since an LLM judge can be flaky in
ways that would otherwise silently fail a whole run. Uses the cheap 'haiku'
tier via core.models.simple_complete, reusing the existing provider-aware
completion helper rather than adding a new LLM client path.
"""

from __future__ import annotations

import json

from core.models import simple_complete

_JUDGE_PROMPT = """You are grading an AI home-asset-management assistant's answer.

User question: {query}
Retrieved/available context (if any): {context}
Assistant's answer: {answer}

Score the answer 1-5 on each axis and return ONLY minified JSON:
{{"groundedness": <1-5>, "relevance": <1-5>, "reasoning": "<one sentence>"}}

groundedness: does the answer avoid unsupported claims not backed by the
context or plausible tool output?
relevance: does the answer actually address the user's question?
"""


def judge_answer(query: str, answer: str, context: str = "") -> dict:
    """Returns {"groundedness": int|None, "relevance": int|None, "reasoning": str}.
    Never raises — a judge failure degrades to None scores, not a crashed eval run."""
    prompt = _JUDGE_PROMPT.format(query=query, context=context or "(none)", answer=answer)
    try:
        raw = simple_complete("haiku", max_tokens=200, prompt=prompt)
    except Exception as exc:
        return {"groundedness": None, "relevance": None, "reasoning": f"judge call failed: {exc}"}

    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return {"groundedness": None, "relevance": None, "reasoning": f"unparseable: {raw[:200]}"}
    try:
        obj = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return {"groundedness": None, "relevance": None, "reasoning": f"unparseable: {raw[:200]}"}

    return {
        "groundedness": obj.get("groundedness"),
        "relevance": obj.get("relevance"),
        "reasoning": obj.get("reasoning", ""),
    }
