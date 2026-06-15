from __future__ import annotations
from pathlib import Path
from email.mime.text import MIMEText
import smtplib
import requests
import pandas as pd

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    EMAIL_SMTP_HOST,
    EMAIL_SMTP_PORT,
    EMAIL_SENDER,
    EMAIL_PASSWORD,
    EMAIL_RECEIVER,
    ALERT_LOG_FILE,
)
from core.utils import ensure_parent, now_str

def _log(message: str) -> None:
    ensure_parent(ALERT_LOG_FILE)
    with open(ALERT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{now_str()}] {message}\n")

def send_telegram(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        _log("Telegram skipped: token/chat id missing")
        return False
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=15)
        ok = resp.ok
        _log(f"Telegram sent={ok}: {message[:120]}")
        return ok
    except Exception as e:
        _log(f"Telegram failed: {e}")
        return False

def send_email(subject: str, body: str) -> bool:
    if not (EMAIL_SENDER and EMAIL_PASSWORD and EMAIL_RECEIVER):
        _log("Email skipped: env vars missing")
        return False
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER

        server = smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, timeout=20)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, [EMAIL_RECEIVER], msg.as_string())
        server.quit()
        _log(f"Email sent: {subject}")
        return True
    except Exception as e:
        _log(f"Email failed: {e}")
        return False

def notify(subject: str, body: str, telegram_first: bool = True) -> None:
    if telegram_first:
        send_telegram(body)
        send_email(subject, body)
    else:
        send_email(subject, body)
        send_telegram(body)
