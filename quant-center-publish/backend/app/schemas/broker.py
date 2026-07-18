from datetime import datetime
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


class BrokerCredentialBase(BaseModel):
    """
    Shared foundational parameters for external broker accounts.
    Kept generic to ensure vendor independence.
    """
    broker_name: str = Field(..., min_length=2, max_length=50, examples=["zerodha", "alpaca", "dhan"])
    client_id: str = Field(..., min_length=2, max_length=100, description="Account identifier / UCC code")
    display_name: Optional[str] = Field(None, max_length=100, description="User-defined descriptor for the profile")
    
    # Restrict execution layer boundaries strictly to valid platform execution types
    environment: Literal["live", "paper", "sandbox"] = Field(
        "live", 
        description="Execution environment tracking matrix: strictly limited to 'live', 'paper', or 'sandbox'"
    )


class BrokerCredentialCreate(BrokerCredentialBase):
    """
    Payload definition for inbound registration operations.
    Captures raw cryptographic credentials securely over transport before persistence layer encryption occurs.
    """
    api_key: str = Field(..., min_length=1, description="Raw API key string issued by the execution venue")
    api_secret: str = Field(..., min_length=1, description="Raw API secret string issued by the execution venue")
    
    # Generic parameter hook to absorb non-standard broker parameters (e.g., TOTP secrets, passwords)
    extra_params: Optional[Dict[str, Any]] = Field(
        None, 
        description="Arbitrary platform configuration values mapped as a flexible key-value dictionary"
    )


class BrokerCredentialUpdate(BaseModel):
    """
    Schema permitting variable partial updates to existing broker configurations.
    All properties remain optional to guarantee mutation isolation.
    """
    display_name: Optional[str] = Field(None, max_length=100)
    environment: Optional[Literal["live", "paper", "sandbox"]] = None
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    extra_params: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class BrokerCredentialResponse(BrokerCredentialBase):
    """
    Data transfer object structuring outbound network replies.
    
    CRITICAL SECURITY BOUNDARY: This response completely omits fields like api_key,
    api_secret, or extra_params to eliminate unintended exposure of sensitive secrets over the API layer.
    """
    id: int
    user_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)