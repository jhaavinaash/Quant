"""
engines/claude_system1_live.py
==============================
S1 swing system runner. All S1 files live together in Quant_Center/engines/:
    claude_system1_live.py   ← this file
    data_downloader_live.py
    indicator_engine.py
    screener.py
    notifier.py
    sector_map.py
    sector_map.csv           ← S1's universe (separate from Quant_Center/data/sector_map_fixed.csv)

S1 keeps its own data and capital logic (₹1,00,000) — unchanged from original.
After the pipeline runs, generated signals are appended to
    ../signals/master_signals.csv   as Engine="S1"
so they appear in the dashboard's Today Actions queue.

Run via dashboard's "Run S1 (3:15 PM)" button, or directly:
    cd Quant_Center/engines
    python claude_system1_live.py
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

HERE           = Path(__file__).resolve().parent              # engines/
MASTER_SIGNALS = HERE.parent / "signals" / "master_signals.csv"


def run(script):
    """Run a sub-script with engines/ as the working directory."""
    print(f"\n{'═' * 55}")
    print(f"  Running {script}...")
    print(f"{'═' * 55}")
    subprocess.run([sys.executable, script], check=True, cwd=str(HERE))


def append_s1_to_master() -> int:
    """
    Read this run's screener output and append it to ../signals/master_signals.csv
    with Engine='S1'. De-duplicates: any S1 rows from today are dropped first
    so reruns don't pile up duplicates.
    """
    screener_csv = HERE / "results" / "screener_signal.csv"

    if not screener_csv.exists():
        print("  No screener_signal.csv — no S1 signals to append.")
        return 0

    try:
        sig = pd.read_csv(screener_csv)
    except Exception as exc:
        print(f"  Could not read screener_signal.csv — {exc}")
        return 0

    if sig.empty:
        print("  Screener generated 0 signals — nothing to append.")
        return 0

    today = datetime.now().strftime("%Y-%m-%d")

    def _strip_currency(v):
        s = str(v).replace("Rs.", "").replace("₹", "").replace(",", "").strip()
        try:
            return float(s)
        except Exception:
            return s

    new_rows = []
    for _, r in sig.iterrows():
        new_rows.append({
            "Date":       today,
            "Engine":     "S1",
            "Ticker":     str(r.get("Ticker", "")).strip(),
            "Entry":      r.get("Entry", ""),
            "SL":         r.get("SL", ""),
            "Target":     r.get("Partial_Target", r.get("Full_Target", "")),
            "Qty":        r.get("Shares", ""),
            "Capital":    _strip_currency(r.get("Capital_Used", "")),
            "SignalType": "BUY",
        })
    new_df = pd.DataFrame(new_rows)

    MASTER_SIGNALS.parent.mkdir(parents=True, exist_ok=True)

    if MASTER_SIGNALS.exists():
        try:
            existing = pd.read_csv(MASTER_SIGNALS)
        except Exception:
            existing = pd.DataFrame()
        if (not existing.empty and "Engine" in existing.columns
                and "Date" in existing.columns):
            mask = (existing["Engine"].astype(str) == "S1") & \
                   (existing["Date"].astype(str).str.startswith(today))
            existing = existing[~mask]
        combined = pd.concat([existing, new_df], ignore_index=True, sort=False)
    else:
        combined = new_df

    # Keep master schema column order
    master_cols = ["Date", "Engine", "Ticker", "Entry", "SL", "Target",
                   "Qty", "Capital", "SignalType"]
    for c in master_cols:
        if c not in combined.columns:
            combined[c] = ""
    other_cols = [c for c in combined.columns if c not in master_cols]
    combined = combined[master_cols + other_cols]

    combined.to_csv(MASTER_SIGNALS, index=False)
    print(f"  ✓ Appended {len(new_df)} S1 signals to {MASTER_SIGNALS}")
    return len(new_df)


if __name__ == "__main__":
    print(f"\n  CLAUDE SYSTEM 1 — {datetime.now().strftime('%d %b %Y %I:%M %p')}")
    print(f"  Starting daily pipeline...")

    try:
        run("data_downloader_live.py")
        run("indicator_engine.py")
        run("screener.py")
        n_appended = append_s1_to_master()
        print(f"\n  ✓ Pipeline complete. {n_appended} S1 signals in master queue.")
        print(f"  ✓ Check dashboard Today Actions tab.\n")
    except subprocess.CalledProcessError as e:
        print(f"\n  ✗ Pipeline failed at step — {e}\n")
        sys.exit(1)
