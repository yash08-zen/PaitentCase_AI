"""
core/security_headers.py
------------------------
Middleware injecting industry-standard HTTP security headers into every response:
- X-Content-Type-Options: nosniff (prevents MIME type sniffing)
- X-Frame-Options: DENY (clickjacking protection)
- X-XSS-Protection: 1; mode=block (legacy browser XSS filter)
- Referrer-Policy: strict-origin-when-cross-origin (privacy protection)
- Permissions-Policy: camera=(), microphone=(), geolocation=() (restricts dangerous APIs)
- Content-Security-Policy (CSP): controls allowed resource origins
- Strict-Transport-Security (HSTS): enforced for HTTPS environments
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Basic security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        # Content Security Policy (allows local assets, blocks frame embedding)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' http://localhost:* http://127.0.0.1:*; "
            "img-src 'self' data: blob: http://localhost:* http://127.0.0.1:*; "
            "frame-ancestors 'none';"
        )

        # Enforce HSTS if running in production
        if getattr(settings, "APP_ENV", "development").lower() == "production":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"

        return response
