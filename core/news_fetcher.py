"""
news_fetcher.py
===============

Diagnosis results (24-May-2026):
  Google News RSS   → HTTP 200, 100 items ✓  (ONLY working source)
  Moneycontrol API  → HTTP 404             ✗  (endpoint gone)
  Moneycontrol RSS  → HTTP 503             ✗  (server blocking)
  NSE API           → HTTP 403/404         ✗  (Akamai-protected + wrong endpoint)

Strategy
--------
Two Google News RSS queries per ticker, run in parallel:

  Q1 — "{company_name}" restricted to trusted Indian finance domains
       → Moneycontrol, Economic Times, LiveMint, Business Standard,
         Reuters, The Hindu BusinessLine, NDTV Profit, Financial Express

  Q2 — "{company_name}" + event keywords
       → Earnings, results, orders, contracts, announcements

Company name is resolved once per ticker via yfinance .info["longName"]
and cached with @lru_cache — so it does not slow down repeated fetches.

Source_Type badge is derived from the provider name in the RSS item:
  "mc"   → provider contains "moneycontrol"
  "nse"  → provider contains "nse", "bse", "sebi"
  "news" → everything else (ET, Mint, BS, Reuters …)
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import feedparser
import pandas as pd
import requests
import yfinance as yf

from config import TRADES_LOG_FILE

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Tunables
# -----------------------------------------------------------------------
MAX_AGE_DAYS     = 14
PER_TICKER_LIMIT = 10      # items kept per ticker (after merge of both queries)
MAX_WORKERS      = 12      # outer threads (one per ticker)

IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc

# -----------------------------------------------------------------------
# Trusted Indian financial news domains (used with site: operator)
# -----------------------------------------------------------------------
TRUSTED_SITES = (
    "site:moneycontrol.com OR site:economictimes.com OR "
    "site:livemint.com OR site:business-standard.com OR "
    "site:reuters.com OR site:thehindubusinessline.com OR "
    "site:ndtvprofit.com OR site:financialexpress.com"
)

# -----------------------------------------------------------------------
# Junk providers — price-tracker aggregators and PR wire noise
# -----------------------------------------------------------------------
_JUNK = {
    "scanx.trade", "simplywall.st", "wisesheets.io",
    "stockanalysis.com", "macrotrends.net",
    "prnewswire.com", "globenewswire.com",
    "ad hoc news", "accesswire", "marketscreener",
}

def _is_junk(provider: str) -> bool:
    p = provider.lower()
    return any(j in p for j in _JUNK)

def _source_type(provider: str) -> str:
    p = provider.lower()
    if any(x in p for x in ("moneycontrol",)):
        return "mc"
    if any(x in p for x in ("nse", "bse", "sebi", "nseindia", "exchange")):
        return "nse"
    return "news"

# -----------------------------------------------------------------------
# Request headers
# -----------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept":          "*/*",
    "Accept-Language": "en-IN,en;q=0.9",
}

GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search"
    "?q={q}&hl=en-IN&gl=IN&ceid=IN:en"
)

# -----------------------------------------------------------------------
# Ticker helpers
# -----------------------------------------------------------------------
def _bare(ticker: str) -> str:
    t = ticker.upper().strip()
    for s in (".NS", ".BO", ".NSE", ".BSE"):
        if t.endswith(s):
            return t[: -len(s)]
    return t

def _ns(ticker: str) -> str:
    t = ticker.upper().strip()
    return t if any(t.endswith(s) for s in (".NS", ".BO")) else f"{t}.NS"

# -----------------------------------------------------------------------
# Company name — resolved once and cached per process lifetime
# -----------------------------------------------------------------------
@lru_cache(maxsize=200)
def _company_name(ticker: str) -> Optional[str]:
    try:
        info = yf.Ticker(_ns(ticker)).info
        return info.get("longName") or info.get("shortName")
    except Exception as e:
        logger.debug("yf info %s: %s", ticker, e)
        return None

# -----------------------------------------------------------------------
# Item helpers
# -----------------------------------------------------------------------
def _time_ago(ts: datetime) -> str:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    s = (datetime.now(UTC) - ts).total_seconds()
    if s < 60:     return "just now"
    if s < 3600:   return f"{int(s / 60)}m ago"
    if s < 86400:  return f"{int(s / 3600)}h ago"
    if s < 172800: return "Yesterday"
    return f"{int(s / 86400)}d ago"

def _rss_ts(entry: Any) -> Optional[datetime]:
    pp = entry.get("published_parsed")
    if not pp:
        return None
    try:
        return datetime(*pp[:6], tzinfo=UTC)
    except Exception:
        return None

def _make(ticker: str, title: str, link: str, provider: str, ts: datetime) -> Dict:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return {
        "Ticker":        ticker,
        "Title":         title.strip(),
        "Link":          link.strip(),
        "Provider":      provider,
        "Published":     ts.astimezone(IST).strftime("%d %b %Y, %H:%M IST"),
        "Published_Ago": _time_ago(ts),
        "Source_Type":   _source_type(provider),
        "_sort_ts":      ts,
    }

# -----------------------------------------------------------------------
# Single Google News RSS query
# -----------------------------------------------------------------------
def _gnews(ticker: str, query: str, limit: int, cutoff: datetime) -> List[Dict]:
    url = GOOGLE_NEWS_RSS.format(q=quote_plus(query))
    try:
        raw  = requests.get(url, headers=HEADERS, timeout=8).content
        feed = feedparser.parse(raw)
    except Exception as e:
        logger.debug("GNews %s: %s", ticker, e)
        return []

    out: List[Dict] = []
    for entry in feed.entries:
        ts    = _rss_ts(entry)
        title = (entry.get("title") or "").strip()
        link  = (entry.get("link")  or "").strip()
        if not (ts and title and link and ts >= cutoff):
            continue
        src      = entry.get("source")
        provider = (
            src.get("title") if isinstance(src, dict) else getattr(src, "title", None)
        ) or "Google News"
        if _is_junk(provider):
            continue
        out.append(_make(ticker, title, link, provider, ts))
        if len(out) >= limit:
            break

    return out

# -----------------------------------------------------------------------
# Per-ticker worker — two queries merged
# -----------------------------------------------------------------------
def _fetch_one(ticker: str, limit: int) -> List[Dict]:
    cutoff = datetime.now(UTC) - timedelta(days=MAX_AGE_DAYS)
    name   = _company_name(ticker)
    bare   = _bare(ticker)
    label  = f'"{name}"' if name else f'"{bare}"'

    # Q1: trusted Indian financial domains only
    q1 = f"{label} ({TRUSTED_SITES})"

    # Q2: event-driven — earnings, results, filings, orders, deals
    q2 = (
        f"{label} (NSE OR BSE) "
        f"(results OR profit OR earnings OR revenue OR "
        f"order OR contract OR acquisition OR Q1 OR Q2 OR Q3 OR Q4 OR "
        f"dividend OR buyback OR announcement OR filing)"
    )

    with ThreadPoolExecutor(max_workers=2) as inner:
        f1 = inner.submit(_gnews, ticker, q1, limit, cutoff)
        f2 = inner.submit(_gnews, ticker, q2, limit, cutoff)
        r1, r2 = f1.result(), f2.result()

    seen:   set = set()
    merged: List[Dict] = []
    for item in r1 + r2:
        if item["Link"] not in seen:
            seen.add(item["Link"])
            merged.append(item)

    merged.sort(key=lambda x: x["_sort_ts"], reverse=True)
    return merged[:limit]

# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------
def get_portfolio_news(
    limit_per_stock: int = PER_TICKER_LIMIT,
    max_workers:     int = MAX_WORKERS,
) -> List[Dict]:
    """
    Fetch news for all OPEN positions in TRADES_LOG_FILE.
    Returns a list sorted newest-first.
    Each dict: Ticker, Title, Link, Provider, Published, Published_Ago, Source_Type
    """
    try:
        trades = pd.read_csv(TRADES_LOG_FILE)
    except Exception as e:
        logger.warning("Cannot read trades log: %s", e)
        return []

    if trades.empty or "Status" not in trades.columns or "Ticker" not in trades.columns:
        return []

    open_df = trades[trades["Status"].astype(str).str.upper() == "OPEN"]
    if open_df.empty:
        return []

    tickers = (
        open_df["Ticker"].dropna().astype(str)
        .str.strip().str.upper().unique().tolist()
    )

    all_news: List[Dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch_one, t, limit_per_stock): t for t in tickers}
        for fut in as_completed(futures):
            try:
                all_news.extend(fut.result())
            except Exception as e:
                logger.warning("Worker %s: %s", futures[fut], e)

    seen:   set = set()
    unique: List[Dict] = []
    for item in all_news:
        if item["Link"] not in seen:
            seen.add(item["Link"])
            unique.append(item)

    unique.sort(key=lambda x: x["_sort_ts"], reverse=True)
    for item in unique:
        item.pop("_sort_ts", None)

    return unique
