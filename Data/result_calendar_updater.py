"""
result_calendar_updater.py
--------------------------
Scans the stock universe for upcoming financial-results board meetings in the
window [today .. today + LOOKAHEAD_DAYS] and writes result_calendar.csv.

The signal generator reads result_calendar.csv and raises an
"AVOID - results due" warning for any ticker whose result date is inside
the window, so we don't take fresh positions into an earnings surprise.

Run standalone:        python result_calendar_updater.py
Or import and call:    from result_calendar_updater import get_results_within_window
"""

import time
import datetime as dt
from pathlib import Path

import pandas as pd
from nselib import capital_market

# ===================== CONFIG =====================
BASE_DIR = Path(__file__).resolve().parent

UNIVERSE_FILE = BASE_DIR / "sector_map_fixed.csv"
OUTPUT_FILE = BASE_DIR / "result_calendar.csv"

LOOKAHEAD_DAYS = 5          # scan today .. today + 5 days
MAX_RETRIES = 4             # NSE endpoints are flaky; retry a few times
RETRY_BACKOFF_SEC = 3       # wait grows: 3s, 6s, 9s ...

# Event-calendar "purpose" values we treat as an earnings event.
# NSE lists many purposes (Dividend, Buy Back, AGM, Fund Raising ...);
# we only care about the ones that move the stock on a surprise.
RESULT_KEYWORDS = ("result", "financial result")


# ===================== UNIVERSE =====================
def load_universe(path: Path) -> set:
    """Load the ticker universe and return a set of bare NSE symbols (no .NS)."""
    try:
        u = pd.read_csv(path, encoding="utf-16")
    except Exception:
        u = pd.read_csv(path)

    u.columns = u.columns.str.strip().str.lower()
    if "ticker" not in u.columns:
        raise KeyError(
            f"'ticker' column not found in {path.name}. "
            f"Columns present: {list(u.columns)}"
        )

    tickers = (
        u["ticker"].astype(str).str.strip().str.upper().str.replace(".NS", "", regex=False)
    )
    return set(t for t in tickers if t and t != "NAN")


# ===================== NSE FETCH =====================
def pick_column(df: pd.DataFrame, candidates) -> str | None:
    """Find a column by case-insensitive match against a list of candidates."""
    lookup = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in lookup:
            return lookup[cand.lower()]
    return None


def fetch_event_calendar(from_date: str, to_date: str) -> pd.DataFrame:
    """
    Fetch the NSE corporate event calendar with retries.

    IMPORTANT: this uses event_calendar_for_equity, NOT
    financial_results_for_equity. The latter downloads and parses an XBRL
    file *per company* (thousands of HTTP calls in earnings season) and
    returns parsed P&L data - not a calendar. event_calendar_for_equity hits
    the lightweight /api/event-calendar endpoint and returns one clean row
    per upcoming event.
    """
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            df = capital_market.event_calendar_for_equity(
                from_date=from_date,
                to_date=to_date,
            )
            if df is None or df.empty:
                # No events in window is a valid outcome, not an error.
                return pd.DataFrame()
            return df
        except Exception as e:
            last_err = e
            print(f"  NSE fetch attempt {attempt}/{MAX_RETRIES} failed: "
                  f"{type(e).__name__}: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SEC * attempt)

    raise RuntimeError(
        f"Could not fetch NSE event calendar after {MAX_RETRIES} attempts. "
        f"Last error: {type(last_err).__name__}: {last_err}"
    )


# ===================== CORE =====================
def get_results_within_window(lookahead_days: int = LOOKAHEAD_DAYS) -> pd.DataFrame:
    """
    Return a DataFrame [Ticker, ResultDate, DaysUntil, Purpose] of universe
    stocks with a results event in the next `lookahead_days` days.
    """
    universe = load_universe(UNIVERSE_FILE)
    print(f"Universe loaded: {len(universe)} tickers")

    today = dt.date.today()
    end = today + dt.timedelta(days=lookahead_days)
    from_date = today.strftime("%d-%m-%Y")
    to_date = end.strftime("%d-%m-%Y")
    print(f"Scanning NSE event calendar {from_date} -> {to_date}\n")

    df = fetch_event_calendar(from_date, to_date)
    if df.empty:
        print("No events returned by NSE for this window.")
        return pd.DataFrame(columns=["Ticker", "ResultDate", "DaysUntil", "Purpose"])

    # NSE column names vary slightly; detect them instead of hard-coding.
    sym_col = pick_column(df, ["symbol", "Symbol"])
    date_col = pick_column(df, ["bm_date", "BoardMeetingDate", "date", "eventDate"])
    purpose_col = pick_column(df, ["purpose", "Purpose", "subject", "description"])

    if sym_col is None or date_col is None:
        raise KeyError(
            "Could not locate symbol/date columns in NSE response. "
            f"Columns returned: {list(df.columns)}"
        )

    rows = []
    for _, r in df.iterrows():
        symbol = str(r.get(sym_col, "")).strip().upper()
        if symbol not in universe:
            continue

        purpose = str(r.get(purpose_col, "")) if purpose_col else ""
        if purpose_col and not any(k in purpose.lower() for k in RESULT_KEYWORDS):
            continue  # skip dividends, AGMs, buybacks, etc.

        raw_date = r.get(date_col)
        if pd.isna(raw_date):
            continue
        try:
            result_date = pd.to_datetime(raw_date, dayfirst=True).date()
        except Exception:
            continue

        if not (today <= result_date <= end):
            continue

        rows.append({
            "Ticker": f"{symbol}.NS",
            "ResultDate": result_date,
            "DaysUntil": (result_date - today).days,
            "Purpose": purpose.strip() or "Financial Results",
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out

    return (
        out.sort_values(["ResultDate", "Ticker"])
           .drop_duplicates(subset=["Ticker"], keep="first")
           .reset_index(drop=True)
    )


def build_result_calendar() -> pd.DataFrame:
    """Build the calendar, save it to OUTPUT_FILE, and print a summary."""
    out = get_results_within_window()

    if out.empty:
        # Still write an empty file so the signal generator never crashes
        # on a missing file - an empty calendar just means "no avoids today".
        pd.DataFrame(columns=["Ticker", "ResultDate", "DaysUntil", "Purpose"]) \
          .to_csv(OUTPUT_FILE, index=False)
        print("No matching result dates in the universe for this window.")
        print(f"Wrote empty calendar: {OUTPUT_FILE}")
        return out

    out.to_csv(OUTPUT_FILE, index=False)
    print(out.to_string(index=False))
    print(f"\nSaved: {OUTPUT_FILE}")
    print(f"Tickers to AVOID (results within {LOOKAHEAD_DAYS}d): {len(out)}")
    return out


if __name__ == "__main__":
    build_result_calendar()
