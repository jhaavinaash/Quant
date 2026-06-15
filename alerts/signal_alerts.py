"""
core/signal_alerts.py
─────────────────────
Reads today's signals from master_signals.csv and dispatches them
via Telegram and Email.

Called as a subprocess by the dashboard after engines run.
Can also be run standalone: python signal_alerts.py
"""
from __future__ import annotations

import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from datetime import date

# ── path setup ────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve()
_ROOT = _HERE.parent.parent          # project root — where config.py lives
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE.parent))  # core/ — sibling modules

import requests
import pandas as pd

from config import (
    MASTER_SIGNALS_FILE,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    EMAIL_SMTP_HOST,
    EMAIL_SMTP_PORT,
    EMAIL_SENDER,
    EMAIL_PASSWORD,
    EMAIL_RECEIVER,
)

# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════

def _fmt(v, prefix: str = "Rs.") -> str:
    """Format a numeric value as a currency string."""
    try:
        return f"{prefix}{float(v):,.2f}"
    except Exception:
        val = str(v).strip()
        return val if val else "—"


def _load_todays_signals() -> pd.DataFrame:
    """Return only today's rows from master_signals.csv."""
    today = date.today().isoformat()          # e.g. "2026-05-29"
    df = pd.read_csv(MASTER_SIGNALS_FILE, dtype=str)
    if "Date" in df.columns:
        df = df[df["Date"].astype(str).str.startswith(today)]
    return df.reset_index(drop=True)


# ══════════════════════════════════════════════════════════════════════
# MESSAGE BUILDERS
# ══════════════════════════════════════════════════════════════════════

def _build_text(df: pd.DataFrame) -> str:
    """Plain-text message for Telegram."""
    today_str = date.today().strftime("%d %b %Y")
    lines = [
        f"QUANT CONTROL CENTER",
        f"Signals — {today_str}",
        "",
    ]

    for eng, grp in df.groupby("Engine", sort=True):
        lines.append(f"[ ENGINE {eng} ]")
        lines.append("─" * 32)
        for _, row in grp.iterrows():
            ticker = row.get("Ticker", "—")
            entry  = _fmt(row.get("Entry",  ""))
            sl     = _fmt(row.get("SL",     ""))
            target = _fmt(row.get("Target", "")) if str(row.get("Target","")).strip() not in ("", "nan") else "—"
            qty    = str(row.get("Qty",     "—"))
            cap    = _fmt(row.get("Capital",""))
            lines += [
                f"  {ticker}",
                f"  Entry  : {entry}",
                f"  SL     : {sl}",
                f"  Target : {target}",
                f"  Qty    : {qty}   Capital: {cap}",
                "",
            ]

    n_sig = len(df)
    n_eng = df["Engine"].nunique() if "Engine" in df.columns else 0
    lines.append(f"Total: {n_sig} signal(s) across {n_eng} engine(s)")
    return "\n".join(lines)


def _build_html(df: pd.DataFrame) -> str:
    """Dark-themed HTML email body."""
    today_str = date.today().strftime("%d %b %Y")
    cards = ""

    for eng, grp in df.groupby("Engine", sort=True):
        cards += f"""
        <div style="margin-bottom:24px;">
          <div style="color:#3b82f6;font-weight:700;font-size:13px;
                      letter-spacing:1.5px;margin-bottom:10px;">
            ENGINE {eng}
          </div>
        """
        for _, row in grp.iterrows():
            ticker = row.get("Ticker", "—")
            entry  = _fmt(row.get("Entry",  ""))
            sl     = _fmt(row.get("SL",     ""))
            target = _fmt(row.get("Target", "")) if str(row.get("Target","")).strip() not in ("", "nan") else "—"
            qty    = str(row.get("Qty",     "—"))
            cap    = _fmt(row.get("Capital",""))
            cards += f"""
          <div style="background:#1e293b;border-radius:8px;padding:14px;
                      margin-bottom:8px;border-left:3px solid #10b981;">
            <div style="font-size:16px;font-weight:700;color:#f1f5f9;
                        margin-bottom:8px;">{ticker}</div>
            <table style="width:100%;border-collapse:collapse;
                          font-size:13px;color:#94a3b8;">
              <tr>
                <td style="padding:2px 8px 2px 0;">
                  <span style="color:#f1f5f9;font-weight:600;">Entry</span>
                </td>
                <td style="padding:2px 16px 2px 0;">{entry}</td>
                <td style="padding:2px 8px 2px 0;">
                  <span style="color:#ef4444;font-weight:600;">SL</span>
                </td>
                <td style="padding:2px 16px 2px 0;">{sl}</td>
                <td style="padding:2px 8px 2px 0;">
                  <span style="color:#10b981;font-weight:600;">Target</span>
                </td>
                <td style="padding:2px 0;">{target}</td>
              </tr>
              <tr>
                <td style="padding:2px 8px 2px 0;">
                  <span style="color:#f1f5f9;font-weight:600;">Qty</span>
                </td>
                <td style="padding:2px 16px 2px 0;">{qty}</td>
                <td style="padding:2px 8px 2px 0;">
                  <span style="color:#f1f5f9;font-weight:600;">Capital</span>
                </td>
                <td colspan="3" style="padding:2px 0;">{cap}</td>
              </tr>
            </table>
          </div>
            """
        cards += "</div>"

    n_sig = len(df)
    n_eng = df["Engine"].nunique() if "Engine" in df.columns else 0

    return f"""
    <html>
    <body style="margin:0;padding:24px;background:#0f172a;
                 font-family:Arial,Helvetica,sans-serif;color:#f8fafc;">
      <div style="max-width:580px;margin:0 auto;">
        <div style="background:#111827;border-radius:12px;padding:24px;
                    border:1px solid #334155;">

          <!-- header -->
          <div style="display:flex;align-items:center;margin-bottom:20px;">
            <div style="width:10px;height:10px;background:#10b981;
                        border-radius:50%;margin-right:10px;"></div>
            <span style="font-size:18px;font-weight:700;color:#f1f5f9;">
              Quant Control Center
            </span>
          </div>
          <p style="color:#64748b;font-size:13px;margin:0 0 24px;">
            Signals — {today_str}
          </p>

          <!-- signal cards -->
          {cards}

          <!-- footer -->
          <div style="border-top:1px solid #334155;margin-top:8px;
                      padding-top:14px;color:#475569;font-size:12px;">
            {n_sig} signal(s) &nbsp;&bull;&nbsp; {n_eng} engine(s)
          </div>

        </div>
      </div>
    </body>
    </html>
    """


# ══════════════════════════════════════════════════════════════════════
# CHANNEL SENDERS
# ══════════════════════════════════════════════════════════════════════

def _send_telegram(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN:
        print("TELEGRAM: credentials missing — set TELEGRAM_BOT_TOKEN in config.py")
        return False
    if not TELEGRAM_CHAT_ID:
        print("TELEGRAM: credentials missing — set TELEGRAM_CHAT_ID in config.py")
        return False
    try:
        url  = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        resp = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=15,
        )
        if resp.ok and resp.json().get("ok"):
            print("TELEGRAM: sent ok")
            return True
        print(f"TELEGRAM: API error — {resp.text[:200]}")
        return False
    except Exception as exc:
        print(f"TELEGRAM: exception — {exc}")
        return False


def _send_email(subject: str, html: str) -> bool:
    if not EMAIL_SENDER:
        print("EMAIL: credentials missing — set EMAIL_SENDER in config.py")
        return False
    if not EMAIL_PASSWORD:
        print("EMAIL: credentials missing — set EMAIL_PASSWORD in config.py")
        return False
    if not EMAIL_RECEIVER:
        print("EMAIL: credentials missing — set EMAIL_RECEIVER in config.py")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_SENDER
        msg["To"]      = EMAIL_RECEIVER
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT) as srv:
            srv.ehlo()
            srv.starttls()
            srv.ehlo()
            srv.login(EMAIL_SENDER, EMAIL_PASSWORD)
            srv.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print("EMAIL: sent ok")
        return True
    except Exception as exc:
        print(f"EMAIL: failed — {exc}")
        return False


# ══════════════════════════════════════════════════════════════════════
# PUBLIC ENTRY POINT
# ══════════════════════════════════════════════════════════════════════

def dispatch_signals() -> dict:
    """
    Read today's signals and send via both channels.
    Returns {"signals": int, "telegram": bool, "email": bool}.
    """
    try:
        df = _load_todays_signals()
    except Exception as exc:
        print(f"SIGNALS: cannot read signals file — {exc}")
        return {"signals": 0, "telegram": False, "email": False}

    if df.empty:
        print("SIGNALS: no signals for today — nothing to send")
        return {"signals": 0, "telegram": False, "email": False}

    n = len(df)
    print(f"SIGNALS: {n} signal(s) found — dispatching...")

    text     = _build_text(df)
    html     = _build_html(df)
    subject  = f"Quant Signals — {date.today().strftime('%d %b %Y')}"

    tg_ok    = _send_telegram(text)
    email_ok = _send_email(subject, html)

    return {"signals": n, "telegram": tg_ok, "email": email_ok}


if __name__ == "__main__":
    result = dispatch_signals()
    print(f"\nResult: {result}")