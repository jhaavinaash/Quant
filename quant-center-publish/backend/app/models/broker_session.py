from datetime import datetime
from sqlalchemy import String, Boolean, ForeignKey, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class BrokerSession(Base, TimestampMixin):
    """
    Generic database model tracking active token lifecycles and token states
    for external execution venues.
    
    This abstracts away daily morning login handshakes (e.g., Zerodha Kite access_tokens, Fyers sessions)
    into a uniform structure, leaving specific lifecycle mutations to adapter layers.
    """
    __tablename__ = "broker_sessions"

    # Enforce a strict state boundary: Only allow a single active session record per credential profile
    __table_args__ = (
        UniqueConstraint(
            "broker_credential_id",
            "is_active",
            name="uq_active_broker_session"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Direct ties to workspace owner and target credential configuration
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    broker_credential_id: Mapped[int] = mapped_column(
        ForeignKey("broker_credentials.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # Encrypted active session authorization strings
    encrypted_access_token: Mapped[str] = mapped_column(String(2000), nullable=False)
    
    # Session temporal lifecycle coordinates
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    
    # Core state identifier - kept consistent with 'is_active' naming standard across layers
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    
    # Dynamic session extension matrix for tracking elements like refresh tokens or public keys
    encrypted_extra_session_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)