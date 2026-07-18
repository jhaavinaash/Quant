from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class User(Base):
    """
    SQLAlchemy database model representing an authenticated system operator
    within the Quant Center trading platform environment.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Enforce unique index lookups at the database layer to accelerate credentials matching
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    
    # Store securely salted cryptographic hash sequences exclusively
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # System accessibility status flag, defaulting to active
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)