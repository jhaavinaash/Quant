"""
Idempotent instrument master sync from the NSE Nifty Total Market CSV.

Default source: {QUANT_BASE_DIR}/data/nifty_totalmarket_list.csv

This script does NOT modify source CSVs. It upserts into PostgreSQL via
InstrumentService.bulk_upsert(), which is safe to re-run.
"""
from __future__ import annotations

import argparse
import asyncio
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import func, select, text

from app.core.config import settings
from app.core.database import SessionLocal, engine
from app.models.instrument import Instrument
from app.schemas.instrument import InstrumentCreate
from app.services.instrument import InstrumentService


def default_instrument_source() -> Path:
    return Path(settings.QUANT_BASE_DIR) / "data" / "nifty_totalmarket_list.csv"
BATCH_SIZE = 250

SERIES_SEGMENT = {
    "EQ": "NSE_EQ",
    "BE": "NSE_BE",
}


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip().lstrip("\ufeff") for col in df.columns]
    return df


def load_valid_rows(source: Path) -> tuple[pd.DataFrame, int]:
    if not source.exists():
        raise FileNotFoundError(f"Instrument master source not found: {source}")

    df = _normalize_columns(pd.read_csv(source))
    required = {"Symbol", "Series", "ISIN Code"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Source CSV missing required columns: {sorted(missing)}")

    total_rows = len(df)
    df["Symbol"] = df["Symbol"].astype(str).str.strip().str.upper()
    df["Series"] = df["Series"].astype(str).str.strip().str.upper()
    df["ISIN Code"] = df["ISIN Code"].astype(str).str.strip()

    valid_mask = (
        df["Symbol"].ne("")
        & df["Symbol"].ne("NAN")
        & df["ISIN Code"].ne("")
        & df["ISIN Code"].ne("NAN")
        & df["Series"].isin(SERIES_SEGMENT)
    )
    valid_df = df.loc[valid_mask].drop_duplicates(subset=["Symbol", "Series"], keep="first")
    return valid_df, total_rows


def row_to_instrument(row: pd.Series) -> InstrumentCreate:
    symbol = row["Symbol"]
    series = row["Series"]
    return InstrumentCreate(
        exchange="NSE",
        segment=SERIES_SEGMENT[series],
        symbol=symbol,
        trading_symbol=f"{symbol}-{series}",
        instrument_token=None,
        isin=row["ISIN Code"],
        asset_type="EQUITY",
        expiry=None,
        strike=None,
        option_type=None,
        tick_size=Decimal("0.05"),
        lot_size=1,
        currency="INR",
        is_active=True,
    )


def build_instruments(df: pd.DataFrame) -> list[InstrumentCreate]:
    return [row_to_instrument(row) for _, row in df.iterrows()]


async def count_instruments() -> int:
    async with SessionLocal() as db:
        result = await db.execute(select(func.count()).select_from(Instrument))
        return int(result.scalar_one() or 0)


async def count_duplicate_keys() -> int:
    async with SessionLocal() as db:
        result = await db.execute(
            text(
                """
                SELECT COUNT(*) FROM (
                    SELECT exchange, trading_symbol
                    FROM instruments
                    GROUP BY exchange, trading_symbol
                    HAVING COUNT(*) > 1
                ) dups
                """
            )
        )
        return int(result.scalar_one() or 0)


async def sync_instruments(source: Path) -> dict:
    valid_df, total_source_rows = load_valid_rows(source)
    instruments = build_instruments(valid_df)
    valid_count = len(instruments)

    before_count = await count_instruments()

    async with SessionLocal() as db:
        synced_total = 0
        for start in range(0, valid_count, BATCH_SIZE):
            batch = instruments[start : start + BATCH_SIZE]
            synced_total += await InstrumentService.bulk_upsert(db, instruments_in=batch)

    after_count = await count_instruments()
    duplicate_groups = await count_duplicate_keys()

    return {
        "source_path": str(source),
        "total_source_rows": total_source_rows,
        "valid_source_rows": valid_count,
        "synced_batches": synced_total,
        "db_count_before": before_count,
        "db_count_after": after_count,
        "duplicate_key_groups": duplicate_groups,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description="Sync NSE instrument master into PostgreSQL")
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Path to nifty_totalmarket_list.csv (default: QUANT_BASE_DIR/data/nifty_totalmarket_list.csv)",
    )
    args = parser.parse_args()
    source = args.source or default_instrument_source()
    summary = await sync_instruments(source)
    await engine.dispose()

    print("Instrument master sync complete.")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
