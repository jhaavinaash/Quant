"""F1 BUY candidate selection — reads canonical f1_decisions.csv only."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import settings
from app.services.f1_basket.constants import BASKET_SIZE


@dataclass
class F1BuyCandidate:
    ticker: str
    portfolio_rank: float
    action: str
    technical_state: str
    sector_state: str
    business_gate: str
    sector: str
    reference_price: float
    f1_timestamp: str
    held_globally: bool = False
    held_conflict: bool = False


def _decisions_path() -> Path:
    return Path(settings.QUANT_BASE_DIR) / "F0" / "data" / "f1" / "f1_decisions.csv"


def _open_positions_path() -> Path:
    return Path(settings.QUANT_BASE_DIR) / "F0" / "production" / "open_positions.csv"


def _trades_log_path() -> Path:
    return Path(settings.QUANT_BASE_DIR) / "portfolio" / "trades_log.csv"


def _bare(t: str) -> str:
    return str(t).strip().upper().replace(".NS", "").replace(".BO", "")


def _load_held_tickers() -> set[str]:
    held: set[str] = set()
    for path in (_open_positions_path(), _trades_log_path()):
        if not path.exists():
            continue
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        ticker_col = next(
            (c for c in df.columns if c.lower() in ("ticker", "symbol")),
            None,
        )
        if ticker_col is None:
            continue
        if "Status" in df.columns:
            open_df = df[df["Status"].astype(str).str.upper() == "OPEN"]
        else:
            open_df = df
        for t in open_df[ticker_col].astype(str):
            held.add(_bare(t))
    return held


def load_f1_decisions_df(path: Path | None = None) -> pd.DataFrame:
    p = path or _decisions_path()
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


def f1_decision_timestamp(df: pd.DataFrame) -> str:
    if df.empty or "Timestamp" not in df.columns:
        return ""
    return str(df["Timestamp"].iloc[0])


def extract_buy_candidates(
    df: pd.DataFrame | None = None,
    *,
    decisions_path: Path | None = None,
) -> tuple[list[F1BuyCandidate], str, int]:
    """
    Extract F1 BUY rows sorted by PortfolioRank ascending (lower = better).
    Research: basket_backtester._select_basket_tickers sort_values portfolio_rank.
    Does NOT exclude held tickers from candidate list (research selects from all BUYs).
    """
    data = df if df is not None else load_f1_decisions_df(decisions_path)
    ts = f1_decision_timestamp(data)
    if data.empty:
        return [], ts, 0

    action_col = "Action" if "Action" in data.columns else "action"
    rank_col = "PortfolioRank" if "PortfolioRank" in data.columns else "portfolio_rank"
    buys = data[data[action_col].astype(str).str.upper() == "BUY"].copy()
    if buys.empty:
        return [], ts, 0

    buys[rank_col] = pd.to_numeric(buys[rank_col], errors="coerce")
    buys = buys.sort_values(rank_col, na_position="last")

    held = _load_held_tickers()
    candidates: list[F1BuyCandidate] = []
    for _, row in buys.iterrows():
        ticker = str(row.get("Ticker", "") or "").strip()
        if not ticker:
            continue
        ref_price = float(pd.to_numeric(row.get("Close", 0), errors="coerce") or 0)
        is_held = _bare(ticker) in held
        candidates.append(
            F1BuyCandidate(
                ticker=ticker,
                portfolio_rank=float(row[rank_col]) if pd.notna(row.get(rank_col)) else 9999.0,
                action=str(row.get(action_col, "BUY")),
                technical_state=str(row.get("TechnicalState", "") or ""),
                sector_state=str(row.get("SectorState", "") or ""),
                business_gate=str(row.get("BusinessGate", "") or ""),
                sector=str(row.get("Sector", "") or ""),
                reference_price=ref_price,
                f1_timestamp=ts,
                held_globally=is_held,
                held_conflict=is_held,
            )
        )
    return candidates, ts, len(data)


def select_top_n(
    candidates: list[F1BuyCandidate],
    n: int = BASKET_SIZE,
) -> list[F1BuyCandidate]:
    return candidates[:n]


def eligibility_from_candidates(
    candidates: list[F1BuyCandidate],
    f1_timestamp: str,
    total_decisions: int,
) -> dict[str, Any]:
    available = len(candidates)
    required = BASKET_SIZE
    missing = max(0, required - available)
    ready = available >= required
    return {
        "f1_decision_timestamp": f1_timestamp,
        "total_decisions": total_decisions,
        "buy_candidate_count": available,
        "required_constituents": required,
        "available_candidates": available,
        "missing_candidates": missing,
        "ready": ready,
        "status": "READY" if ready else "NOT_READY",
        "top_candidates": candidates,
        "selected_preview": select_top_n(candidates) if ready else [],
    }
