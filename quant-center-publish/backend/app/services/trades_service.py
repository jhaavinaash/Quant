"""Closed trades from portfolio/trades_log.csv — dashboard/app_ai.py Tab 3 semantics."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from app.core.config import settings
from app.schemas.trades import ClosedTradeRow, TradesSnapshot, TradesSummary

# dashboard/app_ai.py — closed trades filter
_CLOSED_STATUSES = {"CLOSED"}


def _trades_log_path() -> Path:
    return Path(settings.QUANT_BASE_DIR) / "portfolio" / "trades_log.csv"


def _safe_read_csv(path: Path) -> pd.DataFrame:
    try:
        if path.exists():
            return pd.read_csv(path)
    except Exception:
        pass
    return pd.DataFrame()


def _prepare_trades(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    for col in ["EntryPrice", "Qty", "Target", "StopLoss", "CMP", "PnL", "ExitPrice", "HoldDays", "Days_Held"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], format="%d-%m-%Y", errors="coerce")
    if "ExitDate" in df.columns:
        df["ExitDate"] = pd.to_datetime(df["ExitDate"], format="%d-%m-%Y", errors="coerce")
    return df


def _closed_mask(df: pd.DataFrame) -> pd.Series:
    if df.empty or "Status" not in df.columns:
        return pd.Series(dtype=bool)
    return df["Status"].astype(str).str.upper().isin(_CLOSED_STATUSES)


def _outcome(row: pd.Series) -> str:
    """dashboard/app_ai.py Tab 3 _outcome — TP / SL / Manual."""
    try:
        exit_p = float(row["ExitPrice"])
        tgt = float(row["Target"])
        sl = float(row["StopLoss"])
        if exit_p >= tgt * 0.98:
            return "TP"
        if exit_p <= sl * 1.02:
            return "SL"
        return "Manual"
    except Exception:
        return ""


def _format_date(value) -> str:
    if pd.isna(value):
        return ""
    try:
        return pd.Timestamp(value).strftime("%d-%m-%Y")
    except Exception:
        return str(value)


def _days_held(row: pd.Series) -> Optional[int]:
    """Actual holding duration for closed trades — dashboard/app_ai.py Tab 3.

    Tab 3 overwrites Days_Held with (ExitDate - Date).days. HoldDays is the
    engine max-hold limit at entry and must not be shown as days held.
    """
    if pd.notna(row.get("ExitDate")) and pd.notna(row.get("Date")):
        try:
            return int((row["ExitDate"] - row["Date"]).days)
        except Exception:
            pass
    if pd.notna(row.get("Days_Held")):
        try:
            return int(float(row["Days_Held"]))
        except Exception:
            pass
    return None


def _return_pct(row: pd.Series) -> Optional[float]:
    try:
        entry = float(row["EntryPrice"])
        exit_p = float(row["ExitPrice"])
        if entry == 0:
            return None
        return round((exit_p - entry) / entry * 100.0, 2)
    except Exception:
        return None


def _build_summary(closed: pd.DataFrame) -> TradesSummary:
    """dashboard/app_ai.py header KPIs — CLOSED rows only."""
    if closed.empty or "PnL" not in closed.columns:
        return TradesSummary()

    pnl = closed["PnL"].fillna(0)
    total = len(closed)
    winners = int((pnl > 0).sum())
    losers = int((pnl < 0).sum())
    win_rate = round(winners / total * 100.0, 1) if total else 0.0
    return TradesSummary(
        closedTrades=total,
        realizedPnl=round(float(pnl.sum()), 2),
        winRate=win_rate,
        winners=winners,
        losers=losers,
    )


def _row_to_schema(row: pd.Series, idx: int) -> ClosedTradeRow:
    pnl_val = row.get("PnL")
    pnl = float(pnl_val) if pd.notna(pnl_val) else None
    qty_val = row.get("Qty")
    qty = float(qty_val) if pd.notna(qty_val) else None
    entry_val = row.get("EntryPrice")
    exit_val = row.get("ExitPrice")
    outcome = _outcome(row)
    status = str(row.get("Status") or "").strip()
    flag = str(row.get("Flag") or "").strip()
    action = str(row.get("Action") or "").strip()
    notes = str(row.get("Notes") or "").strip()
    exit_reason = outcome or flag or action or status

    return ClosedTradeRow(
        id=f"{row.get('Ticker', '')}-{idx}",
        ticker=str(row.get("Ticker") or ""),
        engine=str(row.get("Engine") or ""),
        entryDate=_format_date(row.get("Date")),
        exitDate=_format_date(row.get("ExitDate")),
        quantity=qty,
        entryPrice=float(entry_val) if pd.notna(entry_val) else None,
        exitPrice=float(exit_val) if pd.notna(exit_val) else None,
        returnPct=_return_pct(row),
        pnl=round(pnl, 2) if pnl is not None else None,
        holdDays=_days_held(row),
        exitReason=exit_reason,
        outcome=outcome,
        status=status,
        notes=notes,
    )


class TradesService:
    @classmethod
    def get_snapshot(cls) -> TradesSnapshot:
        trades = _prepare_trades(_safe_read_csv(_trades_log_path()))
        closed = trades[_closed_mask(trades)].copy() if not trades.empty else pd.DataFrame()

        if not closed.empty:
            closed["Return_%"] = closed.apply(_return_pct, axis=1)
            closed["Outcome"] = closed.apply(_outcome, axis=1)
            sort_col = "ExitDate" if "ExitDate" in closed.columns else "Date"
            closed = closed.sort_values(sort_col, ascending=False, na_position="last")

        summary = _build_summary(closed)
        engines = sorted(closed["Engine"].dropna().astype(str).unique().tolist()) if not closed.empty else []
        outcomes = sorted({o for o in closed["Outcome"].dropna().astype(str).unique().tolist() if o}) if not closed.empty else []

        rows = [_row_to_schema(row, i) for i, (_, row) in enumerate(closed.iterrows())]

        return TradesSnapshot(
            summary=summary,
            engines=engines,
            outcomes=outcomes,
            trades=rows,
        )
