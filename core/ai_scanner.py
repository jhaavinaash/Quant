from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Tunables
# ----------------------------------------------------------------------

CAPITAL_PER_PICK = 15_000
ATR_SL_MULT = 1.5
ATR_TP_MULT = 3.0
HISTORY_DAYS = 380
BATCH_SIZE = 50

MIN_AVG_VOLUME_20D = 50_000
MIN_PRICE = 20
MAX_PRICE = 50_000

STRONG_BUY_SCORE = 75
STRONG_BUY_GROUPS = 4
BUY_SCORE = 60
WATCH_SCORE = 50
EXIT_THRESHOLD = 40

NIFTY_TICKER = "^NSEI"

# ----------------------------------------------------------------------
# Result container
# ----------------------------------------------------------------------

@dataclass
class ScanResult:

    ticker: str
    company_name: str
    sector: str

    action: str
    conviction: int
    composite_score: float
    groups_fired: int

    trend_score: float = 50
    momentum_score: float = 50
    setup_score: float = 50
    sector_score: float = 50

    current_price: float = 0.0
    suggested_entry: float = 0.0
    suggested_stop: float = 0.0
    suggested_target: float = 0.0

    suggested_qty: int = 0
    capital_used: float = 0.0
    max_risk_inr: float = 0.0
    rr_ratio: float = 0.0
    expected_return_pct: float = 0.0

    rsi: Optional[float] = None
    atr_14: Optional[float] = None

    pct_from_52w_high: Optional[float] = None
    pct_from_52w_low: Optional[float] = None

    avg_volume_20d: Optional[float] = None

    ret_1m: Optional[float] = None
    ret_3m: Optional[float] = None

    rs_vs_nifty_60d: Optional[float] = None

    bull_signals: List[str] = field(default_factory=list)
    bear_signals: List[str] = field(default_factory=list)

    next_event_days: Optional[int] = None
    next_event_label: Optional[str] = None

    is_existing_position: bool = False
    current_pnl_pct: Optional[float] = None

# ----------------------------------------------------------------------
# Indicators
# ----------------------------------------------------------------------

def _rsi(close: pd.Series, period: int = 14) -> Optional[float]:

    if len(close) < period + 1:
        return None

    delta = close.diff()

    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()

    if loss.iloc[-1] == 0:
        return 100.0 if gain.iloc[-1] > 0 else 50.0

    rs = gain.iloc[-1] / loss.iloc[-1]

    return float(100 - 100 / (1 + rs))


def _atr(df: pd.DataFrame, period: int = 14) -> Optional[float]:

    if len(df) < period + 1:
        return None

    high = pd.to_numeric(df["High"], errors="coerce")
    low = pd.to_numeric(df["Low"], errors="coerce")
    close = pd.to_numeric(df["Close"], errors="coerce")

    tr = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return float(tr.rolling(period).mean().iloc[-1])


def _macd_cross(close: pd.Series) -> Optional[str]:

    if len(close) < 30:
        return None

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()

    macd = ema12 - ema26
    sig = macd.ewm(span=9, adjust=False).mean()

    hist = macd - sig

    if len(hist) < 3:
        return None

    if hist.iloc[-2] <= 0 < hist.iloc[-1]:
        return "bull"

    if hist.iloc[-2] >= 0 > hist.iloc[-1]:
        return "bear"

    return None


def _obv_trend(
    close: pd.Series,
    volume: pd.Series,
    window: int = 20,
) -> Optional[str]:

    if len(close) < window + 1:
        return None

    if len(volume) < window + 1:
        return None

    direction = np.sign(close.diff().fillna(0))

    obv = (direction * volume).cumsum()

    if len(obv) < window:
        return None

    slope = obv.iloc[-1] - obv.iloc[-window]

    if slope > 0:
        return "up"

    if slope < 0:
        return "down"

    return None

# ----------------------------------------------------------------------
# Bulk history
# ----------------------------------------------------------------------

def _bulk_history(
    tickers: List[str],
    days: int,
) -> Dict[str, pd.DataFrame]:

    out: Dict[str, pd.DataFrame] = {}

    start = pd.Timestamp.today() - timedelta(days=days)
    end = pd.Timestamp.today()

    for i in range(0, len(tickers), BATCH_SIZE):

        batch = tickers[i:i + BATCH_SIZE]

        try:

            df = yf.download(
                tickers=batch,
                start=start,
                end=end,
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=True,
            )

        except Exception as e:
            logger.warning("yf batch failed: %s", e)
            continue

        if df is None or df.empty:
            continue

        if isinstance(df.columns, pd.MultiIndex):

            for t in batch:

                try:

                    if t not in df.columns.get_level_values(0):
                        continue

                    sub = df[t].dropna(how="all")

                    if not sub.empty:
                        out[t] = sub

                except Exception:
                    continue

        else:

            if len(batch) == 1:
                out[batch[0]] = df.dropna(how="all")

    return out

def _sector_momentum(
    histories: Dict[str, pd.DataFrame],
    info_map: Dict[str, Tuple[str, str]],
) -> Dict[str, float]:
    """
    Sharper sector scoring:
    - compares sector median return vs market median return
    - rewards positive breadth inside the sector
    - penalizes weak / narrow leadership
    """
    sector_buckets: Dict[str, List[float]] = {}
    all_returns: List[float] = []

    for ticker, hist in histories.items():
        if ticker not in info_map:
            continue

        _, sector = info_map[ticker]

        try:
            close = hist["Close"]

            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]

            close = pd.to_numeric(close, errors="coerce").dropna()

            if len(close) < 21:
                continue

            r = ((close.iloc[-1] / close.iloc[-21]) - 1) * 100
            r = float(r)

            all_returns.append(r)
            sector_buckets.setdefault(sector, []).append(r)

        except Exception:
            continue

    if not all_returns:
        return {}

    market_median = float(np.median(all_returns))
    sector_scores: Dict[str, float] = {}

    for sec, vals in sector_buckets.items():
        if len(vals) < 3:
            continue

        vals_arr = np.array(vals, dtype=float)
        sector_median = float(np.median(vals_arr))

        breadth_all = float((vals_arr > 0).mean())       # % of stocks positive
        breadth_strong = float((vals_arr > 5).mean())    # % of stocks > +5%

        # Sharper score:
        # 1) sector relative to market
        # 2) positive breadth inside sector
        # 3) stronger breadth gets extra reward
        score = (
            (sector_median - market_median)
            + ((breadth_all - 0.5) * 12.0)
            + (breadth_strong * 6.0)
        )

        sector_scores[sec] = round(score, 2)

    return sector_scores
# ----------------------------------------------------------------------
# Per ticker scoring
# ----------------------------------------------------------------------

def _analyze(
    ticker: str,
    history: pd.DataFrame,
    company_name: str,
    sector: str,
    nifty_history: Optional[pd.DataFrame],
    sector_mom: float,
    result_cal: Optional[pd.DataFrame],
) -> Optional[ScanResult]:

    if history is None or history.empty or len(history) < 50:
        return None

    # ---------- CLOSE ----------

    close = history["Close"]

    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]

    close = pd.to_numeric(close, errors="coerce").dropna()

    if len(close) < 50:
        return None

    # ---------- VOLUME ----------

    volume = history["Volume"]

    if isinstance(volume, pd.DataFrame):
        volume = volume.iloc[:, 0]

    volume = pd.to_numeric(volume, errors="coerce").dropna()

    if len(volume) < 20:
        return None

    cur_price = float(close.iloc[-1])

    # ---------- FILTERS ----------

    vol_20d = float(volume.iloc[-20:].mean())

    if vol_20d < MIN_AVG_VOLUME_20D:
        return None

    if not (MIN_PRICE <= cur_price <= MAX_PRICE):
        return None

    # ---------- INDICATORS ----------

    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean()

    rsi = _rsi(close)
    atr = _atr(history)

    macd_x = _macd_cross(close)
    obv = _obv_trend(close, volume)

    # ---------- 52W ----------

    win = min(len(close), 252)

    h52 = float(close.iloc[-win:].max())
    l52 = float(close.iloc[-win:].min())

    pct_hi = (cur_price - h52) / h52 * 100 if h52 else 0
    pct_lo = (cur_price - l52) / l52 * 100 if l52 else 0

    # ---------- RETURNS ----------

    ret_1m = (
        ((cur_price / close.iloc[-21]) - 1) * 100
        if len(close) >= 21 else None
    )

    ret_3m = (
        ((cur_price / close.iloc[-63]) - 1) * 100
        if len(close) >= 63 else None
    )

    # ---------- RS ----------

    rs_vs_nifty = None

    if nifty_history is not None:

        try:

            ncl = nifty_history["Close"]

            if isinstance(ncl, pd.DataFrame):
                ncl = ncl.iloc[:, 0]

            ncl = pd.to_numeric(ncl, errors="coerce").dropna()

            if len(ncl) >= 60 and len(close) >= 60:

                stock_60 = (
                    (close.iloc[-1] / close.iloc[-60]) - 1
                ) * 100

                nifty_60 = (
                    (ncl.iloc[-1] / ncl.iloc[-60]) - 1
                ) * 100

                rs_vs_nifty = stock_60 - nifty_60

        except Exception:
            pass

    # ---------- SCORE BUCKETS ----------

    trend = 50.0
    mom = 50.0
    setup = 50.0

    sector_score = max(
        0,
        min(100, 50 + sector_mom),
    )

    bulls: List[str] = []
    bears: List[str] = []

    fired = {
        "trend": False,
        "momentum": False,
        "setup": False,
        "sector": False,
    }

    # ---------- TREND ----------

    if not (
        np.isnan(sma50.iloc[-1])
        or
        np.isnan(sma200.iloc[-1])
    ):

        s50 = float(sma50.iloc[-1])
        s200 = float(sma200.iloc[-1])

        if cur_price > s50 > s200:
            trend += 20
            bulls.append("Above 50/200 DMA")
            fired["trend"] = True

        elif cur_price < s50 < s200:
            trend -= 20
            bears.append("Below 50/200 DMA")

    # ---------- MOMENTUM ----------

    if rsi is not None:

        if 50 <= rsi <= 65:
            mom += 12
            bulls.append(f"RSI healthy ({rsi:.0f})")
            fired["momentum"] = True

        elif rsi > 75:
            mom -= 8
            bears.append(f"RSI overbought ({rsi:.0f})")

        elif rsi < 35:
            mom -= 5
            bears.append(f"RSI weak ({rsi:.0f})")

    if macd_x == "bull":
        mom += 12
        bulls.append("MACD bull cross")
        fired["momentum"] = True

    elif macd_x == "bear":
        mom -= 12
        bears.append("MACD bear cross")

    if ret_1m is not None:

        if ret_1m > 8:
            mom += 8
            bulls.append(f"1M return +{ret_1m:.1f}%")
            fired["momentum"] = True

        elif ret_1m < -10:
            mom -= 8
            bears.append(f"1M return {ret_1m:.1f}%")

    if ret_3m is not None and ret_3m > 20:
        mom += 10
        bulls.append(f"3M return +{ret_3m:.1f}%")
        fired["momentum"] = True

    if rs_vs_nifty is not None:

        if rs_vs_nifty > 8:
            mom += 12
            bulls.append(f"RS +{rs_vs_nifty:.1f}% vs Nifty")
            fired["momentum"] = True

        elif rs_vs_nifty < -8:
            mom -= 10
            bears.append(f"RS {rs_vs_nifty:.1f}% vs Nifty")

    # ---------- SETUP ----------

    recent_vol = float(volume.iloc[-3:].mean())

    vr = recent_vol / vol_20d if vol_20d > 0 else 0

    if vr > 1.5:
        setup += 12
        bulls.append(f"Volume {vr:.1f}× avg")
        fired["setup"] = True

    if obv == "up":
        setup += 10
        bulls.append("OBV accumulation")
        fired["setup"] = True

    elif obv == "down":
        setup -= 10
        bears.append("OBV distribution")

    if pct_hi >= -5:
        setup += 12
        bulls.append("Near 52w high")
        fired["setup"] = True

    elif pct_hi <= -40:
        setup -= 8
        bears.append(f"{abs(pct_hi):.0f}% off 52w high")

    if pct_lo <= 10:
        setup -= 10
        bears.append("Near 52w low")

    # ---------- SECTOR ----------

    if sector_mom > 5:
        bulls.append(f"Sector momentum +{sector_mom:.1f}%")
        fired["sector"] = True

    elif sector_mom < -5:
        bears.append(f"Sector headwind {sector_mom:.1f}%")

    # ---------- FINAL ----------

    trend = max(0, min(100, trend))
    mom = max(0, min(100, mom))
    setup = max(0, min(100, setup))

    composite = (
        trend * 0.30
        + mom * 0.30
        + setup * 0.25
        + sector_score * 0.15
    )

    groups_fired = sum(fired.values())

    if composite >= STRONG_BUY_SCORE and groups_fired >= STRONG_BUY_GROUPS:
        action = "STRONG BUY"
        conviction = 5

    elif composite >= BUY_SCORE:
        action = "BUY"
        conviction = 4

    elif composite >= WATCH_SCORE:
        action = "WATCH"
        conviction = 3

    elif composite < EXIT_THRESHOLD:
        action = "EXIT"
        conviction = 1

    else:
        action = "NEUTRAL"
        conviction = 2

    atr_val = atr if atr else cur_price * 0.03

    suggested_stop = round(
        cur_price - (atr_val * ATR_SL_MULT),
        2,
    )

    suggested_target = round(
        cur_price + (atr_val * ATR_TP_MULT),
        2,
    )

    qty = max(
        int(CAPITAL_PER_PICK // cur_price),
        1,
    )

    risk_per_share = max(
        cur_price - suggested_stop,
        1,
    )

    return ScanResult(
        ticker=ticker,
        company_name=company_name,
        sector=sector,

        action=action,
        conviction=conviction,
        composite_score=round(composite, 1),
        groups_fired=groups_fired,

        trend_score=round(trend, 1),
        momentum_score=round(mom, 1),
        setup_score=round(setup, 1),
        sector_score=round(sector_score, 1),

        current_price=round(cur_price, 2),
        suggested_entry=round(cur_price, 2),
        suggested_stop=suggested_stop,
        suggested_target=suggested_target,

        suggested_qty=qty,
        capital_used=round(qty * cur_price, 0),
        max_risk_inr=round(qty * risk_per_share, 0),

        rr_ratio=round(
            (suggested_target - cur_price)
            / risk_per_share,
            2,
        ),

        expected_return_pct=round(
            ((suggested_target / cur_price) - 1) * 100,
            1,
        ),

        rsi=round(rsi, 1) if rsi else None,
        atr_14=round(atr, 2) if atr else None,

        pct_from_52w_high=round(pct_hi, 1),
        pct_from_52w_low=round(pct_lo, 1),

        avg_volume_20d=round(vol_20d, 0),

        ret_1m=round(ret_1m, 1) if ret_1m else None,
        ret_3m=round(ret_3m, 1) if ret_3m else None,

        rs_vs_nifty_60d=(
            round(rs_vs_nifty, 1)
            if rs_vs_nifty is not None else None
        ),

        bull_signals=bulls[:8],
        bear_signals=bears[:8],
    )

# ----------------------------------------------------------------------
# Main scan
# ----------------------------------------------------------------------

def scan_universe(
    universe_df: pd.DataFrame,
    result_calendar_df: Optional[pd.DataFrame] = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> Dict:

    if universe_df is None or universe_df.empty:

        return {
            "all_results": [],
            "strong_buys": [],
            "watchlist": [],
            "exits": [],
            "sector_momentum": {},
            "scanned_at": pd.Timestamp.now(),
        }

    tcol = next(
        (
            c for c in universe_df.columns
            if c.lower() in ("ticker", "symbol", "tickers")
        ),
        None,
    )

    scol = next(
        (
            c for c in universe_df.columns
            if "sector" in c.lower()
        ),
        None,
    )

    if tcol is None:

        return {
            "all_results": [],
            "strong_buys": [],
            "watchlist": [],
            "exits": [],
            "sector_momentum": {},
            "scanned_at": pd.Timestamp.now(),
        }

    info_map = {}

    for _, row in universe_df.iterrows():

        raw = str(row[tcol]).strip().upper()

        if not raw or raw == "NAN":
            continue

        yf_t = raw if "." in raw else f"{raw}.NS"

        sector = (
            str(row[scol]).strip()
            if scol else "Unknown"
        )

        info_map[yf_t] = (raw, sector)

    tickers = list(info_map.keys())

    histories = _bulk_history(
        tickers,
        HISTORY_DAYS,
    )

    nifty_hist = None

    try:

        nifty_hist = yf.download(
            NIFTY_TICKER,
            start=pd.Timestamp.today() - timedelta(days=HISTORY_DAYS),
            end=pd.Timestamp.today(),
            progress=False,
            auto_adjust=True,
            threads=False,
        )

    except Exception:
        pass

    sec_mom = _sector_momentum(
        histories,
        info_map,
    )

    results = []

    for t in tickers:

        hist = histories.get(t)

        if hist is None:
            continue

        name, sector = info_map[t]

        try:

            r = _analyze(
                t,
                hist,
                name,
                sector,
                nifty_hist,
                sec_mom.get(sector, 0.0),
                result_calendar_df,
            )

            if r:
                results.append(r)

        except Exception as e:
            logger.debug("skip %s: %s", t, e)

    strong_buys = [
        r for r in results
        if r.action == "STRONG BUY"
    ]

    watchlist = [
        r for r in results
        if r.action in ("BUY", "WATCH")
    ]

    strong_buys.sort(
        key=lambda x: x.composite_score,
        reverse=True,
    )

    watchlist.sort(
        key=lambda x: x.composite_score,
        reverse=True,
    )

    return {
        "all_results": results,
        "strong_buys": strong_buys,
        "watchlist": watchlist,
        "exits": [],
        "sector_momentum": sec_mom,
        "scanned_at": pd.Timestamp.now(),
    }

# ----------------------------------------------------------------------
# Existing position tagging
# ----------------------------------------------------------------------

def mark_existing_positions(
    scan: Dict,
    open_positions_df: Optional[pd.DataFrame],
) -> Dict:

    if open_positions_df is None or open_positions_df.empty:
        return scan

    open_map: Dict[str, float] = {}

    for _, row in open_positions_df.iterrows():

        try:

            bare = (
                str(row.get("Ticker", ""))
                .upper()
                .replace(".NS", "")
                .replace(".BO", "")
            )

            entry = float(row.get("EntryPrice", 0))

            if bare and entry > 0:
                open_map[bare] = entry

        except Exception:
            continue

    if not open_map:
        return scan

    exits: List[ScanResult] = []

    for r in scan.get("all_results", []):

        bare = (
            str(r.ticker)
            .upper()
            .replace(".NS", "")
            .replace(".BO", "")
        )

        if bare in open_map:

            r.is_existing_position = True

            entry = open_map[bare]

            r.current_pnl_pct = (
                (r.current_price - entry)
                / entry
            ) * 100

            if r.composite_score < EXIT_THRESHOLD:
                exits.append(r)

    scan["strong_buys"] = [
        r for r in scan["strong_buys"]
        if not r.is_existing_position
    ]

    scan["watchlist"] = [
        r for r in scan["watchlist"]
        if not r.is_existing_position
    ]

    scan["exits"] = sorted(
        exits,
        key=lambda r: r.composite_score,
    )

    return scan