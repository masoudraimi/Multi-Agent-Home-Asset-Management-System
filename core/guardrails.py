"""Guardrails: PII detection and prompt injection protection."""

from __future__ import annotations

import re

_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CREDIT_CARD = re.compile(r"\b(?:\d{4}[\s\-]?){3}\d{4}\b")
_PASSPORT = re.compile(r"\b[A-Z]{1,2}\d{6,9}\b")

_INJECTION_PATTERNS = re.compile(
    r"ignore\s+(previous|prior|above|all)\s+instructions"
    r"|you\s+are\s+now\s+"
    r"|disregard\s+(your|the|all|system)"
    r"|<\|im_start\|>"
    r"|\[INST\]"
    r"|jailbreak"
    r"|pretend\s+you\s+are",
    re.IGNORECASE,
)


class Guardrails:
    def __init__(self, config: dict):
        self.pii_detection: bool = config.get("pii_detection", False)
        self.prompt_injection: bool = config.get("prompt_injection", True)
        self.max_output_chars: int = config.get("max_output_chars", 16000)

    def is_injected(self, text: str) -> bool:
        if not self.prompt_injection:
            return False
        return bool(_INJECTION_PATTERNS.search(text))

    def contains_pii(self, text: str) -> bool:
        if not self.pii_detection:
            return False
        return bool(_SSN.search(text) or _CREDIT_CARD.search(text) or _PASSPORT.search(text))

    def sanitize_output(self, text: str) -> str:
        if self.pii_detection:
            text = _SSN.sub("[SSN REDACTED]", text)
            text = _CREDIT_CARD.sub("[CC REDACTED]", text)
            text = _PASSPORT.sub("[PASSPORT REDACTED]", text)
        return text[:self.max_output_chars]
