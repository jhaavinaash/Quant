from ..repositories.engine_repo import EngineRepository
from fastapi import HTTPException

class EngineService:
    @staticmethod
    def get_engine_statuses():
        try:
            return EngineRepository.get_latest_status()
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))