from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.config import settings
from app.models.base import Base

# 1. Create the asynchronous engine
engine = create_async_engine(settings.async_database_url, echo=True)

# 2. Define the asynchronous session factory
# Note: We alias this to 'SessionLocal' to satisfy existing imports in deps.py
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

# 3. Dependency to get DB session
async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()