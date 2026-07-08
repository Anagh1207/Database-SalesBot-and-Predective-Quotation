from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.logger import get_logger

logger = get_logger("errors")


def register_error_handlers(app: FastAPI):
    """
    Registers global error handlers on the FastAPI app.
    Call this once in main.py during app creation.
    """

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        logger.warning(f"404 — {request.method} {request.url}")
        return JSONResponse(
            status_code=404,
            content={
                "error": "Not found",
                "path": str(request.url),
                "tip": "Visit /docs to see all available endpoints",
            }
        )

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc):
        logger.error(f"500 — {request.method} {request.url} — {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(exc),
                "tip": "Check logs/app.log for full details",
            }
        )

    @app.exception_handler(422)
    async def validation_error_handler(request: Request, exc):
        logger.warning(f"422 Validation error — {request.method} {request.url}")
        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation error",
                "detail": "Your request body has missing or invalid fields",
                "tip": "Visit /docs to see the correct request format",
            }
        )