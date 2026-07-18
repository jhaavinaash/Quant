from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    """
    Unified declarative baseline for all application schema entities.
    Inherits modern SQLAlchemy 2.0 type-mapping mechanics.
    """
    pass

class TimestampMixin:
    """
    Reusable base mixin ensuring consistent chronological auditing data points
    are automatically injected into dependent relational schemas.
    """
    __abstract__ = True
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        sort_order=998
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        sort_order=999
    )