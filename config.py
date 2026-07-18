from pathlib import Path
import os


def _resolve_dir(base: Path, name: str) -> Path:
    """Find a folder under base, matching name case-insensitively (Windows-safe)."""
    direct = base / name
    if direct.exists():
        return direct
    target = name.lower()
    for child in base.iterdir():
        if child.is_dir() and child.name.lower() == target:
            return child
    return direct


BASE_DIR = Path(__file__).resolve().parent

# Load local .env if present (home/office laptops)
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _key, _val = _line.split("=", 1)
        os.environ.setdefault(_key.strip(), _val.strip().strip('"').strip("'"))

DATA_DIR = _resolve_dir(BASE_DIR, "Data")
SIGNALS_DIR = _resolve_dir(BASE_DIR, "Signals")
PORTFOLIO_DIR = _resolve_dir(BASE_DIR, "Portfolio")
ENGINE_DIR = _resolve_dir(BASE_DIR, "Engines")
LOGS_DIR = _resolve_dir(BASE_DIR, "logs")
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# --- Core files ---
MASTER_SIGNALS_FILE = SIGNALS_DIR / "master_signals.csv"
ENGINE_STATUS_FILE = DATA_DIR / "engine_status.csv"
ALERT_LOG_FILE = LOGS_DIR / "alerts.log"
BLOCKED_LOG_FILE = PORTFOLIO_DIR / "blocked_signals.csv"
TRADES_LOG_FILE = PORTFOLIO_DIR / "trades_log.csv"
RESULT_CALENDAR_FILE = DATA_DIR / "result_calendar.csv"
PRICE_FILE = DATA_DIR / "stock_prices_clean.csv"
UNIVERSE_FILE = DATA_DIR / "sector_map_fixed.csv"
NIFTY500_UNIVERSE_FILE = DATA_DIR / "nifty500_universe.csv"
FLASHER_TRACKED_FILE = DATA_DIR / "flasher_tracked_trades.csv"

# --- Engines ---
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

# --- Alerts (set in .env — see .env.example) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
EMAIL_SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "")

# --- Dashboard ---
DASHBOARD_TITLE = "Trading Control Center"
REFRESH_SECONDS = int(os.getenv("DASHBOARD_REFRESH_SECONDS", "0"))

# --- Google Sheets Portfolio ---
PORTFOLIO_GSHEET_ID = os.getenv("PORTFOLIO_GSHEET_ID", "")
