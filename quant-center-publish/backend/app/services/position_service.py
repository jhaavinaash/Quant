import csv
import sys
from pathlib import Path

from app.core.config import settings
from app.schemas.position import PositionResponse
from app.services.position_alert import classify_position_alert


def _load_exit_intents(trade_keys: list[str]) -> dict[str, dict]:
    if not trade_keys:
        return {}
    quant_root = settings.QUANT_BASE_DIR
    if quant_root not in sys.path:
        sys.path.insert(0, quant_root)
    try:
        from execution.exit_intent_store import list_all_intents_by_trade_keys
        from execution.position_exit_service import PositionExitService

        raw = list_all_intents_by_trade_keys(trade_keys)
        out: dict[str, dict] = {}
        for key, intent in raw.items():
            status = str(intent.get("status", "")).upper()
            label = PositionExitService.exit_status_label(status)
            out[key] = {
                "status": status,
                "label": label,
                "reason": str(intent.get("exit_reason", "")),
                "active": status in {"PENDING", "SUBMITTED", "PARTIAL"},
            }
        return out
    except Exception:
        return {}


class PositionService:
    @staticmethod
    def _stable_id(ticker: str, entry_date: str, engine: str) -> str:
        return f"{ticker}|{entry_date}|{engine}"

    @staticmethod
    def _to_float(value: object, default: float = 0.0) -> float:
        if value is None:
            return default
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return default
        try:
            return float(text)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return None
        try:
            return float(text)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _compute_pnl(cls, row: dict) -> float:
        entry = cls._to_float(row.get("Entry"))
        qty = cls._to_float(row.get("Qty"))
        current = cls._optional_float(row.get("CurrentPrice"))
        return_pct = cls._optional_float(row.get("Return_Pct"))

        if current is not None and entry and qty:
            return round((current - entry) * qty, 2)
        if return_pct is not None and entry and qty:
            return round((return_pct / 100.0) * entry * qty, 2)
        return 0.0

    @classmethod
    def _row_to_position(cls, row: dict) -> PositionResponse | None:
        ticker = str(row.get("Ticker", "")).strip()
        entry_date = str(row.get("EntryDate", "")).strip()
        engine = str(row.get("Engine", "")).strip()
        if not ticker:
            return None

        current_price = cls._optional_float(row.get("CurrentPrice"))
        sl = cls._optional_float(row.get("SL"))
        target = cls._optional_float(row.get("Target"))
        pnl = cls._compute_pnl(row)

        return PositionResponse(
            id=cls._stable_id(ticker, entry_date, engine),
            instrument=ticker,
            quantity=cls._to_float(row.get("Qty")),
            avgPrice=cls._to_float(row.get("Entry")),
            pnl=pnl,
            entryDate=entry_date,
            currentPrice=current_price,
            returnPct=cls._optional_float(row.get("Return_Pct")),
            engine=engine,
            sector=str(row.get("Sector", "")).strip(),
            holdDays=cls._optional_float(row.get("HoldDays")),
            sl=sl,
            target=target,
            technicalState=str(row.get("TechnicalState", "")).strip(),
            sectorState=str(row.get("SectorState", "")).strip(),
            exitRule=str(row.get("ExitRule", "")).strip(),
            status=classify_position_alert(
                current_price=current_price,
                stop_loss=sl,
                target=target,
                live_pnl=pnl,
            ),
        )

    @classmethod
    def get_open_positions(cls, source_path: Path | None = None) -> list[PositionResponse]:
        path = source_path or Path(settings.OPEN_POSITIONS_FILE)
        if not path.exists():
            return []

        positions: list[PositionResponse] = []
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                position = cls._row_to_position(row)
                if position is not None:
                    positions.append(position)

        intents = _load_exit_intents([p.id for p in positions])
        enriched: list[PositionResponse] = []
        for position in positions:
            intent = intents.get(position.id)
            if intent:
                enriched.append(
                    position.model_copy(
                        update={
                            "exitStatus": intent.get("label", ""),
                            "exitReason": intent.get("reason", ""),
                            "canExit": not intent.get("active", False),
                        }
                    )
                )
            else:
                enriched.append(position)
        return enriched

    @classmethod
    def get_canonical_summary(cls) -> tuple[int, float, float]:
        """Open count, unrealized P&L, and capital from canonical open_positions.csv."""
        positions = cls.get_open_positions()
        count = len(positions)
        unrealized = round(sum(position.pnl for position in positions), 2)
        capital = round(sum(position.avgPrice * position.quantity for position in positions), 2)
        return count, unrealized, capital
