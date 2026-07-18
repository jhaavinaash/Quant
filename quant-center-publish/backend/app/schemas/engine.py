from pydantic import BaseModel
from datetime import datetime

class EngineStatus(BaseModel):
    Timestamp: datetime
    Engine: str
    Status: str
    Detail: str

    class Config:
        from_attributes = True