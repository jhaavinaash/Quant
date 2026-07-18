from pathlib import Path
from typing import List, Optional, Union
from pydantic import AnyHttpUrl, field_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralized Application Configuration Matrix.
    Loads and validates environment variables at startup, enforcing a strict 
    fail-fast policy for core security and infrastructure dependencies.
    """
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_ignore_empty=True, 
        extra="ignore"
    )

    # Added field to resolve the AttributeError
    ENVIRONMENT: str = Field("dev", description="Current deployment environment (e.g., dev, prod)")

    # Core API Configurations
    PROJECT_NAME: str = "Quant Center"
    API_V1_PREFIX: str = "/api/v1"
    
    # Database Connectivity Vector
    DATABASE_URL: str

    @property
    def async_database_url(self) -> str:
        # Replaces postgresql:// with postgresql+asyncpg:// for async support
        return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Cryptographic & Session Security Boundaries
    SECRET_KEY: str             # JWT validation/signature master token
    ENCRYPTION_SECRET_KEY: str  # 32-byte Fernet base64 key for broker secrets data protection

    # Cross-Origin Resource Sharing (CORS) Access Matrix
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    # Canonical read-only open positions snapshot (orchestrator output)
    OPEN_POSITIONS_FILE: str = Field(
        default=r"C:\Users\Avinaash\Quant\F0\production\open_positions.csv",
        description="Path to open_positions.csv produced by position_tracker",
    )

    # Quant production root (dashboard/app_ai.py data + controls)
    QUANT_BASE_DIR: str = Field(
        default=r"C:\Users\Avinaash\Quant",
        description="Root of the Quant production system",
    )

    ENGINE_STATUS_FILE: Optional[str] = Field(
        default=None,
        description="Override path to engine_status.csv; defaults to QUANT_BASE_DIR/data/engine_status.csv",
    )

    DASHBOARD_REFRESH_SECONDS: int = Field(
        default=0,
        description="Mirrors config.REFRESH_SECONDS label from Streamlit dashboard",
    )

    @property
    def engine_status_path(self) -> Path:
        if self.ENGINE_STATUS_FILE:
            return Path(self.ENGINE_STATUS_FILE)
        return Path(self.QUANT_BASE_DIR) / "data" / "engine_status.csv"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        """Parses comma-separated strings or list configurations safely from configuration files."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        return v

# Instantiate the settings object
settings = Settings()