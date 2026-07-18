import logging
import sys
import structlog
from app.core.config import settings

def setup_logging() -> None:
    """Configures centralized structured logging using structlog."""
    
    # 1. Processors that are agnostic to the Logger implementation.
    # We explicitly EXCLUDE structlog.stdlib processors here as they require a stdlib logger.
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # 2. Logic to choose the logger and the specific processor chain.
    if settings.ENVIRONMENT == "dev":
        # Dev: Uses PrintLogger. We only use pure structlog processors.
        processors = shared_processors + [structlog.dev.ConsoleRenderer()]
        logger_factory = structlog.PrintLoggerFactory()
    else:
        # Prod: Uses standard library integration. We can safely add stdlib processors.
        processors = shared_processors + [
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.JSONRenderer()
        ]
        logger_factory = structlog.BytesLoggerFactory()

    # 3. Configure the engine
    structlog.configure(
        processors=processors,
        logger_factory=logger_factory,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )

    # 4. Standard library redirect
    # This captures logs from other libraries (like uvicorn/sqlalchemy) 
    # and routes them through the structlog processing pipeline.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )