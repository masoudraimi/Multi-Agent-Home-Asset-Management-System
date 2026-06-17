"""Skill D: Telegram monthly maintenance digest."""

from workflows.telegram import build_monthly_digest, send_telegram_message


def send_monthly_digest() -> dict:
    """Build and send the monthly maintenance digest to Telegram."""
    text = build_monthly_digest()
    result = send_telegram_message(text)
    return {**result, "digest_preview": text[:300]}


__all__ = ["send_monthly_digest", "build_monthly_digest", "send_telegram_message"]
