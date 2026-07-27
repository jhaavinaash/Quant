from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.core.config import settings
from app.core.database import engine
from app.api.v1.api import api_router
from app.api.v1.endpoints import health
from app.core.logging import setup_logging
from app.core.exceptions import setup_exception_handlers
from app.services.ai_scanner_watcher import (
    start_ai_scanner_watcher_async,
    stop_ai_scanner_watcher_async,
)
from app.services.f1_basket_monitor import (
    start_basket_monitor_async,
    stop_basket_monitor_async,
)

# 1. Initialize logging
setup_logging()
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles core application state initialization."""
    await logger.ainfo("Starting Quant Center...")
    try:
        async with engine.connect() as connection:
            await connection.exec_driver_sql("SELECT 1")
        await logger.ainfo("Database connectivity verified.")
    except Exception as err:
        await logger.acritical("Database initialization failed!", error=str(err))
        raise err
    # AI Scanner live watch (09:30–15:30 IST / 30m / email only NEW) — start
    # before other monitors so schedule is never dropped by later init work.
    await start_ai_scanner_watcher_async()
    await start_basket_monitor_async()
    yield
    await logger.ainfo("Shutting down...")
    await stop_basket_monitor_async()
    await stop_ai_scanner_watcher_async()
    await engine.dispose()

# 2. Initialize FastAPI
app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan
)

# 3. Setup Exception Handlers (This calls the function defined in exceptions.py)
setup_exception_handlers(app)

# 4. CORS Middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).rstrip("/") for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# 5. Include Routers
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(health.router, prefix="/health", tags=["System Status"])

@app.get("/ping", tags=["System Status"])
async def ping_probe():
    return {"ping": "pong"}