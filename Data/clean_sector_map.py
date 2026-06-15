import pandas as pd
from pathlib import Path

# === CONFIG ===
INPUT_FILE = "sector_map_fixed.csv"
OUTPUT_FILE = "sector_map_cleaned.csv"

def clean_sector(s):
    """Standardize sector names (fix typos, casing, duplicates)"""
    if pd.isna(s):
        return s
    s = str(s).strip().lower()
    
    mapping = {
        "distilaries": "Distilleries",
        "distileries": "Distilleries",
        "power": "Power",
        "psu bank": "PSU Bank",
        "paints": "Paints",
        "auto ancillary": "Auto Ancillary",
        "renewable energy": "Renewable Energy",
        "capital goods": "Capital Goods",
        "gas distribution": "Gas Distribution",
        "housing finance": "Housing Finance",
        "gems & jewellery": "Gems & Jewellery",
        "communication services": "Communication Services",
        "consumer cyclical": "Consumer Cyclical",
        "consumer discretionary": "Consumer Discretionary",
        "financial services": "Financial Services",
        "oil & gas": "Oil & Gas",
        "amc": "AMC",
        "ems": "EMS",
        "paper": "Paper",
        "fmcg": "FMCG",
        "nbfc": "NBFC",
        "telecom": "Telecom",
        "tyre": "Tyre",
    }
    return mapping.get(s, s.title())

# === MAIN CLEANING ===
df = pd.read_csv(INPUT_FILE)

print(f"Original rows: {len(df)}")
print(f"Original unique tickers: {df['Ticker'].nunique()}")

# 1. Deduplicate (keep first occurrence)
df = df.drop_duplicates(subset=["Ticker"], keep="first")

# 2. Clean column names
df.columns = df.columns.str.strip()

# 3. Clean Ticker (uppercase, strip)
df["Ticker"] = df["Ticker"].astype(str).str.strip().str.upper()

# 4. Clean & standardize Sector
df["Sector"] = df["Sector"].apply(clean_sector)

# 5. Sort for readability
df = df.sort_values("Ticker").reset_index(drop=True)

print(f"\nAfter cleaning:")
print(f"  Rows: {len(df)}")
print(f"  Unique tickers: {df['Ticker'].nunique()}")
print(f"  Unique sectors: {df['Sector'].nunique()}")

# Save
df.to_csv(OUTPUT_FILE, index=False)
print(f"\n✅ Saved cleaned file as: {OUTPUT_FILE}")

# Quick verification
print("\nSample of fixed problematic sectors:")
for check in ["Distilleries", "PSU Bank", "Auto Ancillary", "Renewable Energy"]:
    sample = df[df["Sector"] == check]["Ticker"].head(2).tolist()
    if sample:
        print(f"  {check}: {sample}")

print("\nTop sectors by count:")
print(df["Sector"].value_counts().head(10))