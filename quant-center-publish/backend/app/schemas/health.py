from typing import Literal
from pydantic import BaseModel

HealthStatus = Literal["healthy", "warning", "offline"]


class SystemHealth(BaseModel):
    database: HealthStatus
    api: HealthStatus
    quantBaseDir: HealthStatus
    quantExecution: HealthStatus
    engines: HealthStatus
