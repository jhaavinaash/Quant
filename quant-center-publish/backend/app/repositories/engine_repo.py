import pandas as pd

from app.core.config import settings


class EngineRepository:
    @staticmethod
    def get_latest_status():
        """Reads engine_status.csv. Raises FileNotFoundError or Exception on failure."""
        path = settings.engine_status_path
        if not path.exists():
            raise FileNotFoundError(f"Integration source engine_status.csv not found at {path}.")

        try:
            df = pd.read_csv(path)
            if df.empty:
                return []
            return df.to_dict(orient="records")
        except Exception as e:
            raise Exception(f"Failed to parse engine_status.csv: {str(e)}") from e
