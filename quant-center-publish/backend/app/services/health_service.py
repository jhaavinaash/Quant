import sys
from pathlib import Path

from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.schemas.health import HealthStatus, SystemHealth


class HealthService:
    @staticmethod
    async def _check_database() -> HealthStatus:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return "healthy"
        except Exception:
            return "offline"

    @staticmethod
    def _check_quant_base_dir() -> HealthStatus:
        path = Path(settings.QUANT_BASE_DIR)
        if path.is_dir():
            return "healthy"
        return "offline"

    @staticmethod
    def _check_quant_execution() -> HealthStatus:
        quant_root = Path(settings.QUANT_BASE_DIR)
        execution_dir = quant_root / "execution"
        if not quant_root.is_dir():
            return "offline"
        if not execution_dir.is_dir():
            return "warning"

        quant_str = str(quant_root)
        if quant_str not in sys.path:
            sys.path.insert(0, quant_str)
        try:
            import execution.broker_factory  # noqa: F401

            return "healthy"
        except Exception:
            return "warning"

    @staticmethod
    def _check_engines() -> HealthStatus:
        path = settings.engine_status_path
        if not path.exists():
            return "offline"
        try:
            with path.open(encoding="utf-8") as handle:
                lines = [line.strip() for line in handle if line.strip()]
            if len(lines) <= 1:
                return "warning"
            return "healthy"
        except Exception:
            return "warning"

    @classmethod
    async def get_system_health(cls) -> SystemHealth:
        return SystemHealth(
            database=await cls._check_database(),
            api="healthy",
            quantBaseDir=cls._check_quant_base_dir(),
            quantExecution=cls._check_quant_execution(),
            engines=cls._check_engines(),
        )
