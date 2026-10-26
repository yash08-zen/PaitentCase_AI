"""
core/logging_config.py
----------------------
Structured server logging with PII and credential redaction.
Masks authorization tokens, passwords, and sensitive identifiers to prevent leakages in log aggregators.
"""
import re
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import HTTPException

logger = logging.getLogger("patientcase.access")

# Patterns for sensitive field redaction
REDACTION_PATTERNS = [
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_\.]+', re.IGNORECASE), "Bearer [REDACTED]"),
    (re.compile(r'("password"\s*:\s*)"[^"]+"', re.IGNORECASE), r'\1"[REDACTED]"'),
    (re.compile(r'("access_token"\s*:\s*)"[^"]+"', re.IGNORECASE), r'\1"[REDACTED]"'),
    (re.compile(r'("refresh_token"\s*:\s*)"[^"]+"', re.IGNORECASE), r'\1"[REDACTED]"'),
    (re.compile(r'(password=)[^&]+', re.IGNORECASE), r'\1[REDACTED]'),
]


def redact_sensitive_info(text: str) -> str:
    """Mask credentials and tokens within log text."""
    if not text:
        return ""
    result = text
    for pattern, replacement in REDACTION_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        try:
            response: Response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            status_code = response.status_code

            logger.info(
                f"{client_ip} - \"{method} {path}\" {status_code} ({duration_ms}ms)"
            )
            return response
        except (HTTPException, StarletteHTTPException) as http_exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.warning(
                f"{client_ip} - \"{method} {path}\" {http_exc.status_code} ({duration_ms}ms) - {http_exc.detail}"
            )
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=http_exc.status_code,
                content={"detail": http_exc.detail},
                headers=getattr(http_exc, "headers", None),
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"{client_ip} - \"{method} {path}\" 500 ({duration_ms}ms) - Error: {type(exc).__name__}: {exc}",
                exc_info=True,
            )
            from starlette.responses import JSONResponse
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "An internal server error occurred. Please contact system support.",
                    "error_code": "INTERNAL_SERVER_ERROR",
                },
            )
