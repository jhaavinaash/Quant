import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "engines"))
from config import ENGINE_STATUS_FILE
SIGNALS_FILE = BASE_DIR / "signals" / "master_signals.csv"
SIGNALS_FILE.parent.mkdir(parents=True, exist_ok=True)

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


def run_all():
    all_rows = []
    status_rows = []

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
            for s in signals:
                row = normalize_signal(engine_name, s)
                all_rows.append(row)

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
    df.to_csv(SIGNALS_FILE, index=False)
    status_df = pd.DataFrame(status_rows)

    status_df.to_csv(
        ENGINE_STATUS_FILE,
        index=False
    )
    print("\nMaster signal file updated.")


if __name__ == "__main__":
    run_all()