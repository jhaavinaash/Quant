import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "engines"))
from config import ENGINE_STATUS_FILE
try:
    from config import RESULT_CALENDAR_FILE, BLOCKED_LOG_FILE
except Exception:
    RESULT_CALENDAR_FILE = BASE_DIR / "data" / "result_calendar.csv"
    BLOCKED_LOG_FILE = BASE_DIR / "portfolio" / "blocked_signals.csv"

SIGNALS_FILE = BASE_DIR / "signals" / "master_signals.csv"
SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)

RESULT_WINDOW_DAYS = 5   # block fresh entries if results are within N days


def _load_result_block_set() -> set:
    """
    Return a set of bare tickers (no .NS) that have a results event within
    RESULT_WINDOW_DAYS. Engines still run, but signals for these tickers are
    dropped before being written, so we never take a position into earnings.
    """
    try:
        cal = pd.read_csv(RESULT_CALENDAR_FILE)
    except Exception:
        return set()
    if cal.empty or "Ticker" not in cal.columns:
        return set()

    def _bare(t):
        return str(t).strip().upper().replace(".NS", "").replace(".BO", "")

    # If DaysUntil present, use it directly; else compute from ResultDate
    if "DaysUntil" in cal.columns:
        within = cal[pd.to_numeric(cal["DaysUntil"], errors="coerce")
                     .between(0, RESULT_WINDOW_DAYS)]
    elif "ResultDate" in cal.columns:
        d = pd.to_datetime(cal["ResultDate"], errors="coerce")
        today = pd.Timestamp.today().normalize()
        days = (d.dt.normalize() - today).dt.days
        within = cal[days.between(0, RESULT_WINDOW_DAYS)]
    else:
        within = cal

    return set(within["Ticker"].map(_bare).tolist())

from mrpt_engine1_screener_fixed import get_signals as e1_signals
from engine2_screener import get_signals as e2_signals
from engine3_screener import get_signals as e3_signals
from live_engine import get_signals as e4_signals
from e5_screener import get_signals as e5_signals
from engine6_screener import get_signals as e6_signals
from G1 import get_signals as g1_signals

ENGINE_MAP = {
    "E1": e1_signals,
    "E2": e2_signals,
    "E3": e3_signals,
    "E4": e4_signals,
    "E5": e5_signals,
    "E6": e6_signals,
    "G1": g1_signals,
}


def normalize_signal(engine_name, signal):
    return {
        "Date": datetime.now().strftime("%Y-%m-%d"),
        "Engine": engine_name,
        "Ticker": signal.get("Ticker", ""),
        "Entry": signal.get("Entry", signal.get("Price", "")),
        "SL": signal.get("SL", signal.get("StopLoss", "")),
        "Target": signal.get("Partial_Target", signal.get("Target", "")),
        "Qty": signal.get("Shares", signal.get("Qty", "")),
        "Capital": signal.get("Capital_Used", signal.get("Capital", "")),
        "SignalType": "BUY",
    }


def _preserve_s1_signals(today_str: str) -> pd.DataFrame:
    """
    Read existing master_signals.csv and return today's S1 rows so they
    survive the engine-run overwrite. S1 is the Claude1 swing system,
    populated separately via Run S1 button (3:15 PM), and must not be
    wiped when Run Engines fires.
    """
    if not SIGNALS_FILE.exists():
        return pd.DataFrame()
    try:
        existing = pd.read_csv(SIGNALS_FILE)
    except Exception:
        return pd.DataFrame()
    if existing.empty or "Engine" not in existing.columns or "Date" not in existing.columns:
        return pd.DataFrame()
    mask = (existing["Engine"].astype(str) == "S1") & \
           (existing["Date"].astype(str).str.startswith(today_str))
    return existing[mask].copy()


def run_all():
    all_rows = []
    status_rows = []
    blocked_rows = []

    result_block = _load_result_block_set()
    if result_block:
        print(f"Result-watch active: {len(result_block)} ticker(s) blocked "
              f"(results within {RESULT_WINDOW_DAYS}d)")

    for engine_name, fn in ENGINE_MAP.items():
        print(f"\nRunning {engine_name}...")

        try:
            signals = fn()
            status_rows.append({
                "Timestamp": datetime.now(),
                "Engine": engine_name,
                "Status": "SUCCESS",
                "Detail": f"Signals: {len(signals)}"
            })

            if not signals:
                print(f"{engine_name} completed")
                continue

            # collect signals — consolidated alert sent once by dashboard
            n_blocked = 0
            for s in signals:
                row = normalize_signal(engine_name, s)
                bare = str(row.get("Ticker", "")).strip().upper() \
                    .replace(".NS", "").replace(".BO", "")
                if bare in result_block:
                    # Results due within window — skip this fresh entry
                    blocked_rows.append({
                        "Date": datetime.now().strftime("%Y-%m-%d"),
                        "Engine": engine_name,
                        "Ticker": row.get("Ticker", ""),
                        "Reason": f"Results within {RESULT_WINDOW_DAYS}d",
                    })
                    n_blocked += 1
                    continue
                all_rows.append(row)

            if n_blocked:
                print(f"{engine_name} completed — {n_blocked} signal(s) "
                      f"blocked for upcoming results")
            else:
                print(f"{engine_name} completed")

        except Exception as e:
            print(f"{engine_name} FAILED")
            print(e)
            status_rows.append({
                "Timestamp": datetime.now(),
                "Engine": engine_name,
                "Status": "FAILED",
                "Detail": str(e)
            })

    df = pd.DataFrame(all_rows)

    # ── Preserve today's S1 signals (Claude1 swing system) ────────────
    today_str = datetime.now().strftime("%Y-%m-%d")
    s1_preserved = _preserve_s1_signals(today_str)
    if not s1_preserved.empty:
        df = pd.concat([df, s1_preserved], ignore_index=True, sort=False)
        print(f"\nPreserved {len(s1_preserved)} S1 signal(s) from today.")

    df.to_csv(SIGNALS_FILE, index=False)

    # ── Log any signals blocked for upcoming results ──────────────────
    if blocked_rows:
        try:
            BLOCKED_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(blocked_rows).to_csv(BLOCKED_LOG_FILE, index=False)
            print(f"Blocked {len(blocked_rows)} signal(s) for results — "
                  f"logged to {BLOCKED_LOG_FILE.name}")
        except Exception as exc:
            print(f"Could not write blocked log: {exc}")

    status_df = pd.DataFrame(status_rows)

    status_df.to_csv(
        ENGINE_STATUS_FILE,
        index=False
    )
    print("\nMaster signal file updated.")


if __name__ == "__main__":
    run_all()
