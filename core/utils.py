from __future__ import annotations
import importlib.util
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from datetime import datetime

def now_str() -> str:
    return pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

def today_str() -> str:
    return pd.Timestamp.today().strftime("%Y-%m-%d")

def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

def safe_read_csv(path: Path, default: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    if default is None:
        default = pd.DataFrame()
    try:
        if path.exists():
            return pd.read_csv(path)
    except Exception:
        pass
    return default.copy()

def safe_write_csv(df: pd.DataFrame, path: Path) -> None:
    ensure_parent(path)
    df.to_csv(path, index=False)

def load_module_from_path(module_name: str, path: Path):
    if not path.exists():
        raise FileNotFoundError(str(path))
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not import {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module

def normalize_signal_row(
    row: Dict[str, Any],
    engine: str,
    source_file: str = "",
    default_signal_type: str = "BUY",
) -> Dict[str, Any]:
    def pick(*keys, default=None):
        for k in keys:
            if k in row and row[k] is not None and row[k] == row[k]:
                return row[k]
        return default

    ticker = str(pick("Ticker", "ticker", "Symbol", "symbol", default="")).strip().upper()
    entry = pick("Entry", "entry", "Price", "price", "CMP", "cmp", default=None)
    sl = pick("SL", "sl", "StopLoss", "stop_loss", default=None)
    target = pick("Target", "target", "TP", "tp", "Partial_Target", default=None)
    qty = pick("Qty", "qty", "Shares", "shares", default=None)
    capital = pick("Capital", "capital", "Capital_Used", "capital_used", default=None)
    sector = pick("Sector", "sector", default="")
    score = pick("Score", "score", "ret60", "ret_60", default=None)
    action = str(pick("SignalType", "signal", "Action", default=default_signal_type)).upper().strip()

    return {
        "Date": today_str(),
        "Engine": str(engine).upper(),
        "Ticker": ticker,
        "Action": action if action else default_signal_type,
        "Entry": None if entry is None else float(entry),
        "SL": None if sl is None else float(sl),
        "Target": None if target is None else float(target),
        "Qty": None if qty is None else int(float(qty)),
        "Capital": None if capital is None else float(capital),
        "Sector": str(sector),
        "Score": None if score is None else float(score),
        "SourceFile": source_file,
        "Status": "NEW",
    }

def merge_signal_frames(frames: List[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame(columns=[
            "Date","Engine","Ticker","Action","Entry","SL","Target","Qty","Capital","Sector","Score","SourceFile","Status"
        ])
    df = pd.concat(frames, ignore_index=True)
    for col in ["Entry", "SL", "Target", "Capital", "Score"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "Qty" in df.columns:
        df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").astype("Int64")
    df["Engine"] = df["Engine"].astype(str).str.upper().str.strip()
    df["Ticker"] = df["Ticker"].astype(str).str.upper().str.strip()
    df["Action"] = df["Action"].astype(str).str.upper().str.strip()
    df = df.drop_duplicates(subset=["Date","Engine","Ticker","Action"], keep="last")
    return df.sort_values(["Date","Engine","Ticker"]).reset_index(drop=True)

def append_csv(path: Path, df_new: pd.DataFrame) -> pd.DataFrame:
    if path.exists():
        try:
            old = pd.read_csv(path)
        except Exception:
            old = pd.DataFrame()
        df = pd.concat([old, df_new], ignore_index=True)
    else:
        df = df_new.copy()
    safe_write_csv(df, path)
    return df
