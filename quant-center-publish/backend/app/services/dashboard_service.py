"""Dashboard metrics from dashboard/app_ai.py first-half KPI ribbons.

Calculations and data sources copied from app_ai.py; do not alter formulas here.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

from app.core.config import settings
from app.schemas.dashboard import DashboardSnapshot, EngineCagrCard, MarketIndexQuote
from app.services.position_service import PositionService

# dashboard/app_ai.py — SYSTEM_START_FLOOR
SYSTEM_START_FLOOR = pd.Timestamp("2026-01-01")

# dashboard/app_ai.py — fixed engine CAGR card order
_ENGINE_ORDER = ["E1", "E2", "E3", "E4", "E5", "E6", "G1", "S1", "AI"]
_ENGINE_BLACKLIST = {"A1"}

# yfinance via dashboard/app_ai.py _live_prices(); NIFTY 50 also used in core/ai_scanner.py (^NSEI)
_MARKET_INDEX_TICKERS = [
    ("NIFTY 50", "^NSEI"),
    ("BANK NIFTY", "^NSEBANK"),
    ("NIFTY MIDCAP", "NIFTY_MIDCAP_100.NS"),
    ("NIFTY SMALLCAP", "^CNXSC"),
]

_live_price_cache: dict[str, float] = {}
_live_price_cache_time: float = 0.0
_LIVE_PRICE_TTL = 60


def clear_live_price_cache() -> None:
    global _live_price_cache, _live_price_cache_time
    _live_price_cache = {}
    _live_price_cache_time = 0.0


def _safe_read_csv(path: Path) -> pd.DataFrame:
    try:
        if path.exists():
            return pd.read_csv(path)
    except Exception:
        pass
    return pd.DataFrame()


def _live_prices(tickers_tuple: tuple[str, ...]) -> dict[str, float]:
    """dashboard/app_ai.py _live_prices — yfinance fast_info, 60s cache, parallel."""
    global _live_price_cache, _live_price_cache_time

    now = time.time()
    if now - _live_price_cache_time < _LIVE_PRICE_TTL:
        cached = {t: _live_price_cache[t] for t in tickers_tuple if t in _live_price_cache}
        if len(cached) == len(tickers_tuple):
            return cached

    result: dict[str, float] = {}

    def _one(t: str):
        bare = t.upper().replace(".NS", "").replace(".BO", "")
        yf_t = t if "." in t else f"{t}.NS"
        try:
            fi = yf.Ticker(yf_t).fast_info
            price = getattr(fi, "last_price", None) or getattr(fi, "previous_close", None)
            return bare, float(price) if price else None
        except Exception:
            return bare, None

    with ThreadPoolExecutor(max_workers=10) as pool:
        for fut in as_completed({pool.submit(_one, t): t for t in tickers_tuple}):
            bare, price = fut.result()
            if price is not None:
                result[bare] = price

    _live_price_cache.update(result)
    _live_price_cache_time = now
    return result


def _index_quote(name: str, ticker: str) -> MarketIndexQuote:
    try:
        fi = yf.Ticker(ticker).fast_info
        price = getattr(fi, "last_price", None) or getattr(fi, "previous_close", None)
        prev = getattr(fi, "previous_close", None)
        change_pct = None
        if price is not None and prev:
            change_pct = round((float(price) - float(prev)) / float(prev) * 100.0, 2)
        return MarketIndexQuote(
            name=name,
            ticker=ticker,
            price=round(float(price), 2) if price is not None else None,
            changePct=change_pct,
        )
    except Exception:
        return MarketIndexQuote(name=name, ticker=ticker)


def _avg_daily_deployed(sub_df: pd.DataFrame, today: pd.Timestamp) -> float:
    """dashboard/app_ai.py _avg_daily_deployed."""
    if sub_df.empty:
        return 0.0

    ep = pd.to_numeric(sub_df.get("EntryPrice", pd.Series(dtype=float)), errors="coerce")
    qty = pd.to_numeric(sub_df.get("Qty", pd.Series(dtype=float)), errors="coerce")
    cap = (ep * qty).fillna(0.0).values

    entry_s = pd.to_datetime(
        sub_df["Date"] if "Date" in sub_df.columns else pd.Series(dtype="datetime64[ns]"),
        errors="coerce",
    ).dt.normalize()
    entry_v = entry_s.values

    if "ExitDate" in sub_df.columns:
        exit_s = pd.to_datetime(sub_df["ExitDate"], errors="coerce").dt.normalize()
    else:
        exit_s = pd.Series(pd.NaT, index=sub_df.index)

    if "Status" in sub_df.columns:
        is_open = sub_df["Status"].astype(str).str.upper().ne("CLOSED")
    else:
        is_open = pd.Series(True, index=sub_df.index)

    exit_s = exit_s.copy()
    exit_s[is_open | exit_s.isna()] = today
    exit_v = exit_s.values

    valid = ~pd.isnull(entry_s).values
    if not valid.any():
        return 0.0

    first_day = pd.Timestamp(entry_v[valid].min()).normalize()
    date_range = pd.date_range(start=first_day, end=today, freq="D")
    if date_range.empty:
        return 0.0

    daily = np.empty(len(date_range))
    for j, day in enumerate(date_range):
        d = np.datetime64(day, "ns")
        mask = valid & (entry_v <= d) & (exit_v >= d)
        daily[j] = float(cap[mask].sum())

    nonzero = daily[daily > 0]
    return float(nonzero.max()) if len(nonzero) > 0 else 0.0


def _engine_return_table(trades_df: pd.DataFrame) -> pd.DataFrame:
    """dashboard/app_ai.py _engine_return_table."""
    cols = ["Engine", "CAGR", "ROC", "PnL", "Capital", "Days", "Trades", "Inception"]

    if trades_df.empty or "Engine" not in trades_df.columns:
        return pd.DataFrame(columns=cols)

    def _num(frame: pd.DataFrame, col: str):
        if col in frame.columns:
            return pd.to_numeric(frame[col], errors="coerce")
        return pd.Series(np.nan, index=frame.index, dtype="float64")

    today = pd.Timestamp.today().normalize()

    def _valid_dates(frame: pd.DataFrame):
        if "Date" not in frame.columns:
            return pd.Series([], dtype="datetime64[ns]")
        d = pd.to_datetime(frame["Date"], errors="coerce")
        return d[(d.notna()) & (d >= SYSTEM_START_FLOOR) & (d <= today)]

    rows = []
    engines = sorted(trades_df["Engine"].dropna().astype(str).unique().tolist())

    for eng in engines:
        try:
            sub = trades_df[trades_df["Engine"].astype(str) == eng].copy()
            if sub.empty:
                continue

            if "Status" in sub.columns:
                status = sub["Status"].astype(str).str.upper()
            else:
                status = pd.Series(["OPEN"] * len(sub), index=sub.index)

            closed = sub[status == "CLOSED"].copy()
            open_pos = sub[status == "OPEN"].copy()

            realized = 0.0
            if not closed.empty:
                realized = float(_num(closed, "PnL").fillna(0).sum())

            unrealized = 0.0
            if not open_pos.empty:
                entry = _num(open_pos, "EntryPrice")
                qty = _num(open_pos, "Qty")
                if "LiveCMP" in open_pos.columns:
                    live_cmp = _num(open_pos, "LiveCMP")
                elif "CMP" in open_pos.columns:
                    live_cmp = _num(open_pos, "CMP")
                else:
                    live_cmp = entry.copy()
                unrealized = float(((live_cmp.fillna(entry) - entry) * qty).fillna(0).sum())

            total_pnl = float(realized + unrealized)
            capital = _avg_daily_deployed(sub, today)
            if capital <= 0:
                continue

            vdates = _valid_dates(sub)
            if vdates.empty:
                continue
            start_dt = vdates.min().normalize()
            days = max((today - start_dt).days, 1)

            roc = total_pnl / capital
            if (1.0 + roc) > 0:
                cagr = ((1.0 + roc) ** (365.0 / days) - 1.0) * 100.0
            else:
                cagr = -100.0

            rows.append(
                {
                    "Engine": eng,
                    "CAGR": round(cagr, 1),
                    "ROC": round(roc * 100.0, 1),
                    "PnL": round(total_pnl, 0),
                    "Capital": round(capital, 0),
                    "Days": int(days),
                    "Trades": int(len(sub)),
                    "Inception": start_dt,
                }
            )
        except Exception:
            continue

    out = pd.DataFrame(rows, columns=cols)
    if out.empty:
        return pd.DataFrame(columns=cols)
    return out.sort_values("CAGR", ascending=False)


def _build_engine_cagr_cards(return_df: pd.DataFrame) -> list[EngineCagrCard]:
    cards: list[EngineCagrCard] = []
    return_map: dict[str, pd.Series] = {}
    if not return_df.empty:
        for _, row in return_df.iterrows():
            return_map[str(row["Engine"])] = row

    seen: set[str] = set()
    for eng in _ENGINE_ORDER:
        seen.add(eng)
        if eng in return_map:
            row = return_map[eng]
            cagr_val = row["CAGR"]
            subtitle = (
                f"{int(row['Trades'])} trades"
                if pd.isna(cagr_val)
                else f"ROC {row['ROC']:+.1f}% · {int(row['Trades'])} trades · {int(row['Days'])}d"
            )
            cards.append(
                EngineCagrCard(
                    engine=eng,
                    cagr=None if pd.isna(cagr_val) else float(cagr_val),
                    roc=float(row["ROC"]) if not pd.isna(row["ROC"]) else None,
                    trades=int(row["Trades"]),
                    days=int(row["Days"]),
                    subtitle=subtitle,
                )
            )
        else:
            cards.append(
                EngineCagrCard(engine=eng, subtitle="no closed trades yet")
            )

    if not return_df.empty:
        for _, row in return_df.iterrows():
            eng = str(row["Engine"])
            if eng in seen or eng in _ENGINE_BLACKLIST:
                continue
            seen.add(eng)
            cagr_val = row["CAGR"]
            subtitle = (
                f"{int(row['Trades'])} trades"
                if pd.isna(cagr_val)
                else f"ROC {row['ROC']:+.1f}% · {int(row['Trades'])} trades · {int(row['Days'])}d"
            )
            cards.append(
                EngineCagrCard(
                    engine=eng,
                    cagr=None if pd.isna(cagr_val) else float(cagr_val),
                    roc=float(row["ROC"]) if not pd.isna(row["ROC"]) else None,
                    trades=int(row["Trades"]),
                    days=int(row["Days"]),
                    subtitle=subtitle,
                )
            )

    return cards


class DashboardService:
    @staticmethod
    def _quant_paths() -> dict[str, Path]:
        base = Path(settings.QUANT_BASE_DIR)
        return {
            "signals": base / "signals" / "master_signals.csv",
            "trades": base / "portfolio" / "trades_log.csv",
        }

    @classmethod
    def get_market_indices(cls) -> list[MarketIndexQuote]:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(_index_quote, name, ticker) for name, ticker in _MARKET_INDEX_TICKERS]
            return [fut.result() for fut in as_completed(futures)]

    @classmethod
    def get_snapshot(cls) -> DashboardSnapshot:
        paths = cls._quant_paths()
        signals = _safe_read_csv(paths["signals"])
        trades = _safe_read_csv(paths["trades"])

        if not trades.empty:
            for col in ["EntryPrice", "Qty", "Target", "StopLoss", "CMP", "PnL", "ExitPrice"]:
                if col in trades.columns:
                    trades[col] = pd.to_numeric(trades[col], errors="coerce")
            if "Date" in trades.columns:
                trades["Date"] = pd.to_datetime(trades["Date"], format="%d-%m-%Y", errors="coerce")
            if "ExitDate" in trades.columns:
                trades["ExitDate"] = pd.to_datetime(trades["ExitDate"], format="%d-%m-%Y", errors="coerce")

        if not trades.empty and "Status" in trades.columns:
            closed_trades = trades[trades["Status"].astype(str).str.upper() == "CLOSED"].copy()
        else:
            closed_trades = pd.DataFrame()

        open_count, unrealized_pnl, capital_deployed = PositionService.get_canonical_summary()

        realized_pnl = 0.0
        win_rate = 0.0
        total_closed = 0
        if not closed_trades.empty and "PnL" in closed_trades.columns:
            realized_pnl = float(closed_trades["PnL"].fillna(0).sum())
            total_closed = len(closed_trades)
            if total_closed > 0:
                wins = int((closed_trades["PnL"] > 0).sum())
                win_rate = wins / total_closed * 100

        total_pnl = realized_pnl + unrealized_pnl
        active_signals_count = len(signals) if not signals.empty else 0

        return_df = _engine_return_table(trades.copy())
        today_norm = pd.Timestamp.today().normalize()
        total_alloc = _avg_daily_deployed(trades, today_norm) if not trades.empty else 0.0
        if total_alloc <= 0 and not return_df.empty:
            total_alloc = float(return_df["Capital"].sum())

        portfolio_inception: Optional[pd.Timestamp] = pd.NaT
        if not trades.empty and "Date" in trades.columns:
            ad = pd.to_datetime(trades["Date"], errors="coerce")
            today = pd.Timestamp.today().normalize()
            ad = ad[(ad.notna()) & (ad >= SYSTEM_START_FLOOR) & (ad <= today)]
            if not ad.empty:
                portfolio_inception = ad.min().normalize()

        portfolio_cagr: Optional[float] = None
        portfolio_roc: Optional[float] = None
        portfolio_inception_str: Optional[str] = None
        if pd.notna(portfolio_inception) and total_alloc > 0:
            p_days = max((pd.Timestamp.today().normalize() - portfolio_inception).days, 1)
            p_roc = total_pnl / total_alloc
            portfolio_cagr = (
                ((1.0 + p_roc) ** (365.0 / p_days) - 1.0) * 100.0 if (1.0 + p_roc) > 0 else -100.0
            )
            portfolio_roc = p_roc * 100.0
            portfolio_inception_str = portfolio_inception.strftime("%d %b %Y")

        now_ts = pd.Timestamp.now()
        market_open = (9 <= now_ts.hour < 16) and now_ts.weekday() < 5
        refresh_label = (
            f"Auto {settings.DASHBOARD_REFRESH_SECONDS}s"
            if settings.DASHBOARD_REFRESH_SECONDS
            else "Manual refresh"
        )

        return DashboardSnapshot(
            marketOpen=market_open,
            timestamp=now_ts.strftime("%a, %d %b · %H:%M:%S IST"),
            refreshLabel=refresh_label,
            totalPnl=round(total_pnl, 2),
            realizedPnl=round(realized_pnl, 2),
            unrealizedPnl=round(unrealized_pnl, 2),
            openPositions=open_count,
            capitalDeployed=round(capital_deployed, 2),
            winRate=round(win_rate, 1),
            totalClosed=total_closed,
            activeSignals=active_signals_count,
            portfolioCagr=round(portfolio_cagr, 1) if portfolio_cagr is not None else None,
            portfolioRoc=round(portfolio_roc, 1) if portfolio_roc is not None else None,
            portfolioInception=portfolio_inception_str,
            engineCagrs=_build_engine_cagr_cards(return_df),
            marketIndices=cls.get_market_indices(),
        )
