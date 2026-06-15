from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent

# --- Core files ---
MASTER_SIGNALS_FILE = BASE_DIR / "signals" / "master_signals.csv"
ENGINE_STATUS_FILE = BASE_DIR / "data" / "engine_status.csv"
ALERT_LOG_FILE = BASE_DIR / "logs" / "alerts.log"
BLOCKED_LOG_FILE = BASE_DIR / "portfolio" / "blocked_signals.csv"
TRADES_LOG_FILE = BASE_DIR / "portfolio" / "trades_log.csv"
RESULT_CALENDAR_FILE = BASE_DIR / "data" / "result_calendar.csv"
PRICE_FILE = BASE_DIR / "data" / "stock_prices_clean.csv"
UNIVERSE_FILE = BASE_DIR / "data" / "sector_map_fixed.csv"

# --- Engines ---
# Keep these as canonical names in your project folder.
ENGINE_DIR = BASE_DIR / "engines"

ENGINE_SPECS = [
    {"engine": "E1", "path": ENGINE_DIR / "mrpt_engine1_screener_fixed.py"},
    {"engine": "E2", "path": ENGINE_DIR / "engine2_screener.py"},
    {"engine": "E3", "path": ENGINE_DIR / "engine3_screener.py"},
    {"engine": "E4", "path": ENGINE_DIR / "live_engine.py"},
    {"engine": "E5", "path": ENGINE_DIR / "e5_screener.py"},
    {"engine": "E6", "path": ENGINE_DIR / "engine6_screener.py"},
]

# --- Rules / sizing ---
ENGINE_RULES = {
    "E1": {"tp": 0.053, "sl": 0.03, "hold": 3, "capital": 120000},
    "E2": {"tp": 0.0,   "sl": 0.0,  "hold": 10, "capital": 140000},
    "E3": {"tp": 0.053, "sl": 0.03, "hold": 5, "capital": 120000},
    "E4": {"tp": 0.057, "sl": 0.04, "hold": 14, "capital": 70000},
    "E5": {"tp": 0.0,   "sl": 0.12, "hold": 10, "capital": 70000},
    "E6": {"tp": 0.055, "sl": 0.03, "hold": 7, "capital": 80000},
}

DEFAULT_MAX_POSITIONS = {
    "E1": 3,
    "E2": 3,
    "E3": 3,
    "E4": 3,
    "E5": 3,
    "E6": 3,
}

# --- Alerts ---
TELEGRAM_BOT_TOKEN = "8914697078:AAHEHuUehbua4YIRTK-v04QW9Y09UPQumIk"
TELEGRAM_CHAT_ID   = "5840693995"
EMAIL_SMTP_HOST    = "smtp.gmail.com"
EMAIL_SMTP_PORT    = 587
EMAIL_SENDER       = "jhaavinaash@gmail.com"
EMAIL_PASSWORD     = "rzwr xdnw kbvo dyof"
EMAIL_RECEIVER     = "jhaavinaash@gmail.com"

# --- Dashboard ---
DASHBOARD_TITLE = "Trading Control Center"
REFRESH_SECONDS = int(os.getenv("DASHBOARD_REFRESH_SECONDS", "0"))

# --- Google Sheets Portfolio ---
PORTFOLIO_GSHEET_ID = "1j2_oAF4U4z0yGV2s4GA4MS1oLrql5hbG-YF5hmaENGs"
