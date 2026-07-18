from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
)


def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN:
        print("Telegram bot token missing")
        return

    if not TELEGRAM_CHAT_ID:
        print("Telegram chat id missing")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
    }

    try:
        response = requests.post(url, data=payload, timeout=10)
        print(response.text)

    except Exception as e:
        print("Telegram send failed")
        print(e)


if __name__ == "__main__":
    send_telegram_message("✅ Quant_Center Telegram alerts connected.")
