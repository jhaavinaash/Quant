from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog

logger = structlog.get_logger()

def setup_exception_handlers(app: FastAPI) -> None:
    """
    Configures global exception handlers. 
    This function must be called from main.py after the app is initialized.
    """

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        await logger.awarn(
            "HTTP exception occurred", 
            path=request.url.path, 
            status=exc.status_code, 
            detail=exc.detail
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        await logger.aerror(
            "Unhandled server exception", 
            path=request.url.path, 
            error=str(exc)
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred."},
        )