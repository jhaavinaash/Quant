from sqlalchemy import String, Boolean, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin


class BrokerCredential(Base, TimestampMixin):
    """
    Generic, polymorphically abstract database model storing encrypted authentication vectors
    and routing parameters required to interface with external execution venues.
    
    Inherits temporal tracking behaviors natively via TimestampMixin.
    """
    __tablename__ = "broker_credentials"
    
    # Enforce database-level uniqueness boundaries to block duplicate mapping configurations
    __table_args__ = (
        UniqueConstraint("user_id", "broker_name", "client_id", name="uq_user_broker_client"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Cascade account removals cleanly if a platform operator profile is deleted
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True
    )
    
    # Generic operational parameters
    broker_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # e.g., 'zerodha', 'alpaca', 'dhan'
    client_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)    # Account identifier / login UCC code
    display_name: Mapped[str | None] = mapped_column(String(100), nullable=True)      # Custom label (e.g., 'Primary Live Account')
    environment: Mapped[str] = mapped_column(String(20), default="live", nullable=False) # 'live', 'paper', 'sandbox'
    
    # Standard encrypted authorization fields (Encrypted strings handled at the service layer)
    encrypted_api_key: Mapped[str] = mapped_column(String(512), nullable=False)
    encrypted_api_secret: Mapped[str] = mapped_column(String(1000), nullable=False)
    
    # Dynamic parameter extension matrix for custom vendor fields (e.g., TOTP secrets, PINs, or tokens)
    encrypted_extra_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # Direct execution capability toggle switch
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)