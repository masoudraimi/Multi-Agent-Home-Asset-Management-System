"""Guardrails: PII detection and layered prompt-injection protection.

Injection defense is two layers:
  1. Regex (`is_injected` / layer "regex") — fast, free, deterministic. Catches
     known patterns; not meant to catch everything.
  2. LLM classifier (`core.injection_classifier`, layer "classifier") — a
     cheap model call that only runs when layer 1 is clean, catching
     paraphrased/encoded attempts the regex misses. Escalation is controlled
     per-agent via `injection_classifier_enabled` (agent.yaml).

`scan()` is the entry point new code should use; `is_injected()` (regex-only)
is kept for callers that only need the fast layer (e.g. the orchestrator's
pre-dispatch check, which runs before any agent-specific config is loaded).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CREDIT_CARD = re.compile(r"\b(?:\d{4}[\s\-]?){3}\d{4}\b")
_PASSPORT = re.compile(r"\b[A-Z]{1,2}\d{6,9}\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b")
_PHONE = re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}\b")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b")
_ADDRESS_HINT = re.compile(
    r"\b\d{1,5}\s+\w+(\s\w+){0,3}\s(street|st|avenue|ave|road|rd|drive|dr|lane|ln|court|ct)\b",
    re.IGNORECASE,
)
# Note: a standalone bank-account-number pattern (e.g. bare 8-17 digit runs)
# is deliberately NOT included — it collides constantly with asset serial
# numbers and IDs. Documented limitation rather than a false-positive-prone
# "fix".

_INJECTION_PATTERNS = re.compile(
    r"ignore\s+(previous|prior|above|all)\s+instructions"
    r"|you\s+are\s+now\s+"
    r"|disregard\s+(your|the|all|system)"
    r"|<\|im_start\|>"
    r"|\[INST\]"
    r"|jailbreak"
    r"|pretend\s+you\s+are"
    r"|<\s*system\s*>"
    r"|###\s*system"
    r"|\{\{.*?\}\}",
    re.IGNORECASE,
)

_ZERO_WIDTH_CODEPOINTS = (0x200B, 0x200C, 0x200D, 0xFEFF)  # ZWSP, ZWNJ, ZWJ, BOM/ZWNBSP
_ZERO_WIDTH = str.maketrans("", "", "".join(chr(cp) for cp in _ZERO_WIDTH_CODEPOINTS))


def _strip_evasion_chars(text: str) -> str:
    """Strip zero-width characters used to break up regex matches, and
    normalize unicode so visually-identical lookalike characters collapse
    to their ASCII form where possible."""
    return unicodedata.normalize("NFKC", text.translate(_ZERO_WIDTH))


@dataclass
class GuardrailVerdict:
    blocked: bool
    layer: str | None = None       # "regex" | "classifier" | None
    category: str | None = None


class Guardrails:
    def __init__(self, config: dict):
        self.pii_detection: bool = config.get("pii_detection", False)
        self.prompt_injection: bool = config.get("prompt_injection", True)
        self.max_output_chars: int = config.get("max_output_chars", 16000)
        self.injection_classifier_enabled: bool = config.get("injection_classifier", True)

    def is_injected(self, text: str) -> bool:
        """Fast, regex-only check. Use `scan()` for the full layered check."""
        if not self.prompt_injection:
            return False
        return bool(_INJECTION_PATTERNS.search(_strip_evasion_chars(text)))

    def scan(self, text: str, *, source: str, use_classifier: bool = True) -> GuardrailVerdict:
        """Layered injection check: regex first (cheap short-circuit),
        escalating to the LLM classifier only when regex is clean and both
        `use_classifier` and the agent's `injection_classifier_enabled` allow it.

        `source` is one of "user_message" | "tool_output" | "retrieved_context"
        and is passed through to the classifier so its prompt can adapt.
        """
        if not self.prompt_injection:
            return GuardrailVerdict(blocked=False)
        cleaned = _strip_evasion_chars(text)
        if _INJECTION_PATTERNS.search(cleaned):
            return GuardrailVerdict(blocked=True, layer="regex", category="pattern_match")

        if not (use_classifier and self.injection_classifier_enabled):
            return GuardrailVerdict(blocked=False)

        from core.injection_classifier import classify_injection
        verdict = classify_injection(cleaned, source=source)
        if verdict["injected"]:
            return GuardrailVerdict(blocked=True, layer="classifier", category=verdict["category"])
        return GuardrailVerdict(blocked=False)

    def contains_pii(self, text: str) -> bool:
        if not self.pii_detection:
            return False
        return bool(
            _SSN.search(text)
            or _CREDIT_CARD.search(text)
            or _PASSPORT.search(text)
            or _EMAIL.search(text)
            or _PHONE.search(text)
            or _IBAN.search(text)
            or _ADDRESS_HINT.search(text)
        )

    def sanitize_output(self, text: str) -> str:
        if self.pii_detection:
            text = _SSN.sub("[SSN REDACTED]", text)
            text = _CREDIT_CARD.sub("[CC REDACTED]", text)
            text = _PASSPORT.sub("[PASSPORT REDACTED]", text)
            text = _EMAIL.sub("[EMAIL REDACTED]", text)
            text = _PHONE.sub("[PHONE REDACTED]", text)
            text = _IBAN.sub("[IBAN REDACTED]", text)
            text = _ADDRESS_HINT.sub("[ADDRESS REDACTED]", text)
        return text[:self.max_output_chars]
