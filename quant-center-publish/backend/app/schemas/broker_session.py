from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict


class BrokerSessionBase(BaseModel):
    """
    Shared foundational parameters for active execution sessions.
    Keeps a tight operational link back to the underlying venue credentials.
    """
    broker_credential_id: int = Field(..., description="Foreign key anchor targeting the parent broker profile")


class BrokerSessionCreate(BrokerSessionBase):
    """
    Payload definition for inbound execution session token registration.
    Captures raw transient credentials obtained during daily morning exchange authorization flow.
    """
    access_token: str = Field(..., min_length=1, description="Raw exchange access token string generated during login handshake")
    expires_at: Optional[datetime] = Field(None, description="Explicit UTC timestamp marking token expiration boundary")
    extra_session_data: Optional[Dict[str, Any]] = Field(
        None, 
        description="Dynamic structural block absorbing transient values (e.g. public tokens or channel IDs)"
    )


class BrokerSessionUpdate(BaseModel):
    """
    Schema tracking variable state alterations or dynamic session invalidation.
    Aligned strictly with the 'deactivate' operation state matrix.
    """
    is_active: Optional[bool] = Field(None, description="Direct toggle switch to gracefully invalidate an active session channel")
    expires_at: Optional[datetime] = Field(None, description="Adjusted expiration boundary for token tracking")


class BrokerSessionResponse(BrokerSessionBase):
    """
    Data transfer object structuring outbound session metadata queries.

    CRITICAL SECURITY BOUNDARY: This response completely omits fields like access_token
    and extra_session_data to prevent highly sensitive, live session authorization strings 
    from leaking across network transport footprints to client UI layers.
    """
    id: int
    user_id: int
    is_active: bool
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)