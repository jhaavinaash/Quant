"""
result_calendar_updater.py
--------------------------
Fetches NSE upcoming results calendar using only `requests` + `pandas`
(no nselib dependency). Writes result_calendar.csv to data/ folder.

Run standalone:  python result_calendar_updater.py
Or via dashboard Run Engines button (auto-called before engines fire).
"""

import time
import datetime as dt
from pathlib import Path

import pandas as pd
import requests

# ── Config ────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).resolve().parent          # core/
UNIVERSE_FILE  = BASE_DIR.parent / "data" / "sector_map_fixed.csv"
OUTPUT_FILE    = BASE_DIR.parent / "data" / "result_calendar.csv"

LOOKAHEAD_DAYS = 5
RESULT_KEYWORDS = ("result", "financial result")

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer":         "https://www.nseindia.com/",
}


# ── Universe ─────────────────────────────────────────────────────────
def load_universe() -> set:
    try:
        u = pd.read_csv(UNIVERSE_FILE)
    except Exception as e:
        raise FileNotFoundError(f"Universe file not found at {UNIVERSE_FILE}: {e}")
    col = next((c for c in u.columns if c.strip().lower() == "ticker"), u.columns[0])
    tickers = u[col].astype(str).str.strip().str.upper().str.replace(".NS", "", regex=False)
    return set(t for t in tickers if t and t != "NAN" and "DUMMY" not in t)


# ── NSE session ───────────────────────────────────────────────────────
def get_nse_session() -> requests.Session:
    """
    Hit NSE homepage first to get cookies, then return the primed session.
    NSE API calls fail without a valid session cookie.
    """
    s = requests.Session()
    s.headers.update(NSE_HEADERS)
    try:
        s.get("https://www.nseindia.com/", timeout=15)
    except Exception as e:
        raise ConnectionError(f"Could not reach NSE homepage: {e}")
    return s


# ── Fetch event calendar ──────────────────────────────────────────────
def fetch_event_calendar(session: requests.Session,
                         from_date: str, to_date: str) -> pd.DataFrame:
    """
    Call NSE /api/event-calendar and return a DataFrame.
    from_date / to_date in DD-MM-YYYY format.
    """
    url = "https://www.nseindia.com/api/event-calendar"
    params = {"fromDate": from_date, "toDate": to_date}

    for attempt in range(1, 4):
        try:
            r = session.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            if not data:
                return pd.DataFrame()
            return pd.DataFrame(data)
        except Exception as e:
            print(f"  Attempt {attempt}/3 failed: {e}")
            if attempt < 3:
                time.sleep(3 * attempt)

    raise RuntimeError("NSE event calendar unreachable after 3 attempts.")


# ── Core ──────────────────────────────────────────────────────────────
def build_result_calendar() -> pd.DataFrame:
    universe = load_universe()
    print(f"Universe: {len(universe)} tickers")

    today    = dt.date.today()
    end      = today + dt.timedelta(days=LOOKAHEAD_DAYS)
    from_str = today.strftime("%d-%m-%Y")
    to_str   = end.strftime("%d-%m-%Y")
    print(f"Scanning NSE events {from_str} → {to_str}")

    session = get_nse_session()
    df      = fetch_event_calendar(session, from_str, to_str)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    empty_cols = ["Ticker", "ResultDate", "DaysUntil", "Purpose"]

    if df.empty:
        pd.DataFrame(columns=empty_cols).to_csv(OUTPUT_FILE, index=False)
        print("No events in window. Empty calendar written.")
        return pd.DataFrame(columns=empty_cols)

    # NSE column names vary — detect flexibly
    col_map = {c.lower(): c for c in df.columns}
    sym_col  = next((col_map[k] for k in ("symbol","sym") if k in col_map), None)
    date_col = next((col_map[k] for k in ("bm_date","date","eventdate","boardmeetingdate")
                     if k in col_map), None)
    purp_col = next((col_map[k] for k in ("purpose","subject","description")
                     if k in col_map), None)

    if not sym_col or not date_col:
        raise KeyError(f"Cannot find symbol/date columns. Got: {list(df.columns)}")

    rows = []
    for _, r in df.iterrows():
        symbol  = str(r.get(sym_col, "")).strip().upper()
        if symbol not in universe:
            continue
        purpose = str(r.get(purp_col, "")) if purp_col else ""
        if purp_col and not any(k in purpose.lower() for k in RESULT_KEYWORDS):
            continue
        try:
            result_date = pd.to_datetime(r[date_col], dayfirst=True).date()
        except Exception:
            continue
        if not (today <= result_date <= end):
            continue
        rows.append({
            "Ticker":     f"{symbol}.NS",
            "ResultDate": result_date,
            "DaysUntil":  (result_date - today).days,
            "Purpose":    purpose.strip() or "Financial Results",
        })

    if not rows:
        pd.DataFrame(columns=empty_cols).to_csv(OUTPUT_FILE, index=False)
        print("No result events for universe in this window.")
        return pd.DataFrame(columns=empty_cols)

    out = (pd.DataFrame(rows)
             .sort_values(["ResultDate", "Ticker"])
             .drop_duplicates(subset=["Ticker"], keep="first")
             .reset_index(drop=True))

    out.to_csv(OUTPUT_FILE, index=False)
    print(out.to_string(index=False))
    print(f"\nSaved: {OUTPUT_FILE}")
    print(f"Tickers to block (results within {LOOKAHEAD_DAYS}d): {len(out)}")
    return out


if __name__ == "__main__":
    build_result_calendar()