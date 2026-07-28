"""Send the monthly home maintenance digest via Telegram.

Run manually or via cron:
  0 8 1 * * cd /path/to/home-asset-agent && uv run python scripts/send_monthly_reminder.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from agents.maintenance.workflows.telegram import build_monthly_digest, send_telegram_message


def send_monthly_digest() -> dict:
    text = build_monthly_digest()
    result = send_telegram_message(text)
    return {**result, "digest_preview": text[:300]}


if __name__ == "__main__":
    result = send_monthly_digest()
    if result.get("status") == "sent":
        print(f"Digest sent successfully (message_id={result.get('message_id')})")
        print("\nPreview:")
        print(result.get("digest_preview", ""))
    else:
        print(f"Failed to send: {result}")
        sys.exit(1)
