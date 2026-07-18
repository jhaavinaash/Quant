"""
engines/sector_map.py
─────────────────────
Loads the trading universe from Quant_Center/data/sector_map_fixed.csv
— the same file every other engine uses. Removes the need for a
separate sector_map.csv inside engines/.

Public API preserved: load_universe() returns a DataFrame with
'Ticker' and 'Sector' columns, exactly what screener.py,
data_downloader_live.py, and indicator_engine.py expect.
"""
from pathlib import Path
import pandas as pd

HERE          = Path(__file__).resolve().parent              # engines/
UNIVERSE_FILE = HERE.parent / "data" / "sector_map_fixed.csv"


def load_universe() -> pd.DataFrame:
    """
    Return the universe as a DataFrame with columns Ticker (e.g. 'BHEL.NS')
    and Sector. Drops empty rows and DUMMY placeholders.
    """
    if not UNIVERSE_FILE.exists():
        raise FileNotFoundError(
            f"Universe file not found at {UNIVERSE_FILE}. "
            f"Expected Quant_Center/data/sector_map_fixed.csv."
        )

    df = pd.read_csv(UNIVERSE_FILE)

    # Be defensive about column names — the file has a UTF-8 BOM so first
    # column may show up as '\ufeffTicker' on some readers.
    cols = [c.strip().lstrip("\ufeff") for c in df.columns]
    df.columns = cols

    if "Ticker" not in df.columns:
        df = df.rename(columns={df.columns[0]: "Ticker"})
    if "Sector" not in df.columns and len(df.columns) > 1:
        df = df.rename(columns={df.columns[1]: "Sector"})

    df["Ticker"] = df["Ticker"].astype(str).str.strip()
    df["Sector"] = df["Sector"].astype(str).str.strip()

    # Filter out empty + dummy rows
    df = df[df["Ticker"] != ""].reset_index(drop=True)
    df = df[~df["Ticker"].str.upper().str.contains("DUMMY", na=False)].reset_index(drop=True)

    return df[["Ticker", "Sector"]]
