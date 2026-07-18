"""Trade Entry Journal — mirrors dashboard/app_ai.py Tab 9 (Unified Trade Entry).

Writes directly to portfolio/trades_log.csv. Manual book operations only — no broker orders.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

from app.core.config import settings
from app.schemas.trade_entry import (
    PendingDeployTrade,
    TradeBookRow,
    TradeEntryActionResult,
    TradeEntryAddRequest,
    TradeEntryCloseRequest,
    TradeEntryEditRequest,
    TradeEntrySnapshot,
)

_NUM_COLS = (
    "EntryPrice",
    "Qty",
    "StopLoss",
    "Target",
    "ExitPrice",
    "PnL",
    "CMP",
    "LiveCMP",
)


def _quant_root() -> Path:
    return Path(settings.QUANT_BASE_DIR)


def _trades_log_path() -> Path:
    try:
        root = _quant_root()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        import config  # type: ignore

        val = getattr(config, "TRADES_LOG_FILE", None)
        if val:
            return Path(str(val))
    except Exception:
        pass
    return _quant_root() / "portfolio" / "trades_log.csv"


def _pending_trade_path() -> Path:
    try:
        root = _quant_root()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        import config  # type: ignore

        prod = getattr(config, "PROD_DIR", None)
        if prod:
            return Path(str(prod)) / "pending_trade.json"
    except Exception:
        pass
    return _quant_root() / "F0" / "production" / "pending_trade.json"


def _load_pending_trade() -> Optional[dict]:
    path = _pending_trade_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _clear_pending_trade() -> None:
    path = _pending_trade_path()
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def _as_date(value: Any) -> date:
    try:
        dt = pd.to_datetime(value, errors="coerce", dayfirst=True)
        if pd.notna(dt):
            return dt.date()
    except Exception:
        pass
    return pd.Timestamp.today().date()


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _iso_to_ddmmyyyy(iso_date: str) -> str:
    dt = datetime.strptime(iso_date[:10], "%Y-%m-%d")
    return dt.strftime("%d-%m-%Y")


def _ddmmyyyy_to_iso(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return ""
    try:
        dt = pd.to_datetime(text, dayfirst=True, errors="coerce")
        if pd.notna(dt):
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    return text


def _load_trade_book() -> pd.DataFrame:
    path = _trades_log_path()
    try:
        tb = pd.read_csv(path) if path.exists() else pd.DataFrame()
    except Exception:
        tb = pd.DataFrame()
    if tb.empty:
        return tb
    tb.columns = [str(c).strip() for c in tb.columns]
    for col in _NUM_COLS:
        if col in tb.columns:
            tb[col] = pd.to_numeric(tb[col], errors="coerce")
    if "ExitDate" in tb.columns:
        tb["ExitDate"] = tb["ExitDate"].astype(object)
    return tb


def _save_trade_book(tb: pd.DataFrame) -> None:
    path = _trades_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tb.to_csv(path, index=False)


def _rebuild_open_positions() -> bool:
    try:
        root = _quant_root()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from core.production.position_tracker import build_open_positions

        build_open_positions()
        return True
    except Exception:
        return False


def _cell_str(value: Any) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def _row_to_schema(idx: int, row: pd.Series) -> TradeBookRow:
    known = {
        "Date",
        "Engine",
        "Ticker",
        "Action",
        "EntryPrice",
        "Qty",
        "StopLoss",
        "Target",
        "CMP",
        "PnL",
        "Status",
        "ExitDate",
        "ExitPrice",
        "Notes",
    }
    extra = {
        str(k): (None if pd.isna(v) else v)
        for k, v in row.items()
        if str(k) not in known
    }
    return TradeBookRow(
        rowIndex=int(idx),
        date=_cell_str(row.get("Date")),
        engine=_cell_str(row.get("Engine")),
        ticker=_cell_str(row.get("Ticker")),
        action=_cell_str(row.get("Action")),
        entryPrice=_as_float(row.get("EntryPrice"), 0.0) if pd.notna(row.get("EntryPrice")) else None,
        qty=_as_float(row.get("Qty"), 0.0) if pd.notna(row.get("Qty")) else None,
        stopLoss=_as_float(row.get("StopLoss"), 0.0) if pd.notna(row.get("StopLoss")) else None,
        target=_as_float(row.get("Target"), 0.0) if pd.notna(row.get("Target")) else None,
        cmp=_as_float(row.get("CMP"), 0.0) if pd.notna(row.get("CMP")) else None,
        pnl=_as_float(row.get("PnL"), 0.0) if pd.notna(row.get("PnL")) else None,
        status=_cell_str(row.get("Status")),
        exitDate=_cell_str(row.get("ExitDate")),
        exitPrice=_as_float(row.get("ExitPrice"), 0.0) if pd.notna(row.get("ExitPrice")) else None,
        notes=_cell_str(row.get("Notes")),
        extra=extra,
    )


def _pending_to_schema(data: dict) -> PendingDeployTrade:
    return PendingDeployTrade(
        ticker=str(data.get("ticker", "") or ""),
        engine=str(data.get("engine", "") or ""),
        close=_as_float(data.get("close", 0)),
        suggestedQty=max(_as_float(data.get("suggested_qty", 1), 1.0), 1.0),
        rank=str(data.get("rank", "") or ""),
        sector=str(data.get("sector", "") or ""),
        technical=str(data.get("technical", "") or ""),
        business=str(data.get("business", "") or ""),
    )


def _default_notes_from_deploy(deploy: PendingDeployTrade) -> str:
    parts: list[str] = []
    if deploy.rank:
        parts.append(f"Rank#{deploy.rank}")
    if deploy.sector:
        parts.append(deploy.sector)
    if deploy.technical:
        parts.append(f"Tech:{deploy.technical}")
    if deploy.business:
        parts.append(f"Biz:{deploy.business}")
    return " | ".join(parts)


class TradeEntryService:
    @classmethod
    def get_snapshot(cls) -> TradeEntrySnapshot:
        tb = _load_trade_book()
        trades = [_row_to_schema(idx, row) for idx, row in tb.iterrows()] if not tb.empty else []
        trades.sort(key=lambda r: r.rowIndex, reverse=True)

        pending_raw = _load_pending_trade()
        pending = _pending_to_schema(pending_raw) if pending_raw else None
        return TradeEntrySnapshot(trades=trades, pendingDeploy=pending)

    @classmethod
    def discard_pending_deploy(cls) -> TradeEntryActionResult:
        _clear_pending_trade()
        return TradeEntryActionResult(success=True, message="Pending deploy discarded")

    @classmethod
    def add_trade(cls, body: TradeEntryAddRequest) -> TradeEntryActionResult:
        ticker = body.ticker.upper().strip()
        if not ticker:
            return TradeEntryActionResult(success=False, message="Ticker required")
        if body.entryPrice <= 0:
            return TradeEntryActionResult(success=False, message="Entry price required")
        if body.qty <= 0:
            return TradeEntryActionResult(success=False, message="Quantity required")

        tb = _load_trade_book()
        pending = _load_pending_trade()
        notes = body.notes.strip()
        if not notes and pending:
            notes = _default_notes_from_deploy(_pending_to_schema(pending))

        new_trade = pd.DataFrame(
            [
                {
                    "Date": _iso_to_ddmmyyyy(body.tradeDate),
                    "Engine": str(body.engine).strip(),
                    "Ticker": ticker,
                    "Action": str(body.action).strip().upper(),
                    "EntryPrice": float(body.entryPrice),
                    "Qty": float(body.qty),
                    "StopLoss": float(body.stopLoss),
                    "Target": float(body.target),
                    "CMP": float(body.entryPrice),
                    "PnL": 0.0,
                    "Status": "OPEN",
                    "ExitPrice": np.nan,
                    "ExitDate": np.nan,
                    "Notes": notes,
                }
            ]
        )

        try:
            updated = pd.concat([tb, new_trade], ignore_index=True) if not tb.empty else new_trade.copy()
            _save_trade_book(updated)
            _clear_pending_trade()
            rebuilt = _rebuild_open_positions()
            return TradeEntryActionResult(
                success=True,
                message=f"Trade saved: {ticker} @ ₹{body.entryPrice:,.2f}",
                rebuiltOpenPositions=rebuilt,
            )
        except Exception as exc:
            return TradeEntryActionResult(success=False, message=f"Save failed: {exc}")

    @classmethod
    def edit_trade(cls, row_index: int, body: TradeEntryEditRequest) -> TradeEntryActionResult:
        tb = _load_trade_book()
        if tb.empty or row_index not in tb.index:
            return TradeEntryActionResult(success=False, message=f"Unknown trade row {row_index}")

        try:
            tb.loc[row_index, "Date"] = _iso_to_ddmmyyyy(body.tradeDate)
            tb.loc[row_index, "Engine"] = str(body.engine).strip()
            tb.loc[row_index, "Ticker"] = str(body.ticker).upper().strip()
            tb.loc[row_index, "Action"] = str(body.action).strip().upper()
            tb.loc[row_index, "Qty"] = float(body.qty)
            tb.loc[row_index, "EntryPrice"] = float(body.entryPrice)
            tb.loc[row_index, "StopLoss"] = float(body.stopLoss)
            tb.loc[row_index, "Target"] = float(body.target)
            tb.loc[row_index, "Notes"] = str(body.notes).strip()
            tb.loc[row_index, "Status"] = str(body.status).strip().upper()
            tb.loc[row_index, "CMP"] = float(body.entryPrice)

            if str(body.status).upper() == "CLOSED":
                exit_price = float(body.exitPrice or 0)
                exit_date = body.exitDate or pd.Timestamp.today().strftime("%Y-%m-%d")
                tb.loc[row_index, "ExitPrice"] = exit_price
                tb.loc[row_index, "ExitDate"] = _iso_to_ddmmyyyy(exit_date)
                tb.loc[row_index, "PnL"] = (exit_price - float(body.entryPrice)) * float(body.qty)
            else:
                tb.loc[row_index, "ExitPrice"] = np.nan
                tb.loc[row_index, "ExitDate"] = np.nan
                tb.loc[row_index, "PnL"] = 0.0

            _save_trade_book(tb)
            rebuilt = _rebuild_open_positions()
            return TradeEntryActionResult(
                success=True,
                message="Trade updated",
                rebuiltOpenPositions=rebuilt,
            )
        except Exception as exc:
            return TradeEntryActionResult(success=False, message=f"Edit failed: {exc}")

    @classmethod
    def close_trade(cls, row_index: int, body: TradeEntryCloseRequest) -> TradeEntryActionResult:
        """Manual journal close — same as Streamlit Tab 9 Close Trade (no broker SELL)."""
        tb = _load_trade_book()
        if tb.empty or row_index not in tb.index:
            return TradeEntryActionResult(success=False, message=f"Unknown trade row {row_index}")

        status = str(tb.loc[row_index, "Status"]).upper()
        if status != "OPEN":
            return TradeEntryActionResult(success=False, message="Trade is not OPEN")

        try:
            entry = float(tb.loc[row_index, "EntryPrice"])
            qty = float(tb.loc[row_index, "Qty"])
            pnl = (float(body.exitPrice) - entry) * qty
            tb.loc[row_index, "ExitPrice"] = float(body.exitPrice)
            tb.loc[row_index, "ExitDate"] = _iso_to_ddmmyyyy(body.exitDate)
            tb.loc[row_index, "PnL"] = pnl
            tb.loc[row_index, "Status"] = "CLOSED"
            _save_trade_book(tb)
            rebuilt = _rebuild_open_positions()
            return TradeEntryActionResult(
                success=True,
                message=f"Closed | PnL ₹{pnl:,.0f}",
                pnl=round(pnl, 2),
                rebuiltOpenPositions=rebuilt,
            )
        except Exception as exc:
            return TradeEntryActionResult(success=False, message=f"Close failed: {exc}")

    @classmethod
    def delete_trade(cls, row_index: int) -> TradeEntryActionResult:
        tb = _load_trade_book()
        if tb.empty or row_index not in tb.index:
            return TradeEntryActionResult(success=False, message=f"Unknown trade row {row_index}")

        try:
            tb = tb.drop(row_index)
            _save_trade_book(tb)
            rebuilt = _rebuild_open_positions()
            return TradeEntryActionResult(
                success=True,
                message="Trade deleted",
                rebuiltOpenPositions=rebuilt,
            )
        except Exception as exc:
            return TradeEntryActionResult(success=False, message=f"Delete failed: {exc}")

    @classmethod
    def default_add_from_pending(cls) -> dict[str, Any]:
        """Prefill values for Add form when F1 deploy pending exists."""
        pending_raw = _load_pending_trade()
        if not pending_raw:
            return {}
        deploy = _pending_to_schema(pending_raw)
        return {
            "engine": deploy.engine or "MANUAL",
            "ticker": deploy.ticker,
            "entryPrice": deploy.close if deploy.close > 0 else 0.0,
            "qty": deploy.suggestedQty,
            "notes": _default_notes_from_deploy(deploy),
            "pendingDeploy": deploy.model_dump(),
        }
