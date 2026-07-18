import asyncio

from app.core.database import engine
from app.models import (
    Base,
    User,
    BrokerCredential,
    BrokerSession,
    Instrument,
)

EXPECTED_TABLES = (
    User.__tablename__,
    BrokerCredential.__tablename__,
    BrokerSession.__tablename__,
    Instrument.__tablename__,
)


async def create_tables():
    registered_tables = set(Base.metadata.tables.keys())
    missing_models = [name for name in EXPECTED_TABLES if name not in registered_tables]
    if missing_models:
        raise RuntimeError(
            f"Model tables not registered on unified Base metadata: {missing_models}"
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await engine.dispose()
    print("Database tables created successfully.")
    print(f"Registered tables: {sorted(Base.metadata.tables.keys())}")


if __name__ == "__main__":
    asyncio.run(create_tables())