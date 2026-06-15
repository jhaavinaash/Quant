# Quant Control MVP

This is a practical first pass for your multi-engine control layer.

## What it does
- runs engines with a central orchestrator
- normalizes outputs into one master signal file
- logs engine status
- sends Telegram first, email second
- shows a simple Streamlit dashboard

## Environment variables for alerts
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- EMAIL_SENDER
- EMAIL_PASSWORD
- EMAIL_RECEIVER

## Run
1. Copy this folder into your project root.
2. Make sure the canonical engine filenames match `config.py`.
3. Run:
   - `py core/orchestrator.py`
   - `streamlit run dashboard/app.py`

## Notes
- The dashboard is intentionally practical, not flashy.
- No WhatsApp integration is included.
- No broker API execution is included.
