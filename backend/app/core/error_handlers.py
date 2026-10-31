"""
core/error_handlers.py
----------------------
Centralized exception handlers for FastAPI.
Ensures uniform error structures and prevents stack trace or server path leaks on unexpected 500 errors.
"""
import logging
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("patientcase.errors")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        formatted_errors = []
        for err in exc.errors():
            loc = err.get("loc", [])
            field = loc[-1] if loc else "body"
            formatted_errors.append({
                "field": str(field),
                "message": err.get("msg", "Invalid value"),
                "type": err.get("type", "value_error"),
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Input validation failed. Please verify submitted fields.",
                "errors": formatted_errors,
            },
        )

    @app.exception_handler(HTTPException)
    async def custom_http_exception_handler(request: Request, exc: HTTPException):
        headers = getattr(exc, "headers", None)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def global_unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(
            f"Unhandled exception on {request.method} {request.url.path}: {exc}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal server error occurred. Please contact system support.",
                "error_code": "INTERNAL_SERVER_ERROR",
            },
        )
