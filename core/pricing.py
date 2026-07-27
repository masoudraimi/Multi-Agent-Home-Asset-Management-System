"""Per-model input/output pricing for budget enforcement.

Rates are in USD per million tokens. Add new models as needed; unknown
models estimate zero cost (so the budget guard is effectively disabled).

Kept in code (not a config file) because these change rarely and we want
runtime access without a YAML round-trip.
"""

from __future__ import annotations

# (input_per_1m, output_per_1m) in USD
_RATES: dict[str, tuple[float, float]] = {
    # Anthropic direct (as of 2026-Q2)
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    # OpenRouter-prefixed same models
    "anthropic/claude-sonnet-4-6": (3.00, 15.00),
    "anthropic/claude-haiku-4-5": (1.00, 5.00),
    # Common cheap OpenRouter alternatives (approximate)
    "google/gemini-3.5-flash-lite": (0.30, 2.50),
    "google/gemini-3.6-flash": (1.50, 7.50),
    "deepseek/deepseek-chat": (0.09, 0.28),
    "openai/gpt-4o-mini": (0.15, 0.60),
    # OpenAI direct
    "gpt-4o-mini": (0.15, 0.60),
}


def estimate_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    """Cost estimate for a single completion. Zero for unknown models."""
    rate_in, rate_out = _RATES.get(model, (0.0, 0.0))
    return (tokens_in * rate_in + tokens_out * rate_out) / 1_000_000.0


def rates_for(model: str) -> tuple[float, float]:
    """(input_per_1m, output_per_1m) for a model. (0, 0) if unknown."""
    return _RATES.get(model, (0.0, 0.0))


def is_priced(model: str) -> bool:
    """True if this model has known rates. False disables the budget guard."""
    return model in _RATES
