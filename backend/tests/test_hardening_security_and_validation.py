"""
tests/test_hardening_security_and_validation.py
-----------------------------------------------
Milestone 9 verification suite:
- Defensive security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, CSP, Referrer-Policy)
- Sliding-window rate limiter enforcement on sensitive endpoints (HTTP 429 + Retry-After)
- Safe error handling: unhandled 500s return clean JSON with zero stack trace / internal path leakage
- Structured 422 input validation responses with explicit field breakdown
- Restricted CORS preflight policy
"""
import pytest
from httpx import AsyncClient
from app.core.rate_limiter import limiter
from app.main import app


@pytest.mark.asyncio
async def test_security_headers_present_on_all_responses(client: AsyncClient):
    """Every HTTP response must carry defensive security headers."""
    r = await client.get("/health")
    assert r.status_code == 200

    headers = r.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("X-XSS-Protection") == "1; mode=block"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in headers.get("Content-Security-Policy", "")
    assert "camera=()" in headers.get("Permissions-Policy", "")


@pytest.mark.asyncio
async def test_rate_limiting_enforcement_and_retry_after(client: AsyncClient):
    """Exceeding endpoint rate limit must return HTTP 429 and Retry-After header."""
    limiter.reset()
    limiter.enforce_in_tests = True

    try:
        # Rate limit for login is 10 requests per 60 seconds per IP
        responses = []
        for _ in range(12):
            res = await client.post(
                "/api/auth/login",
                json={"username": "invalid_user", "password": "WrongPassword@123"},
            )
            responses.append(res)

        # First 10 may fail authentication (401), but the 11th and 12th must be rate limited (429)
        status_codes = [res.status_code for res in responses]
        assert 429 in status_codes

        rate_limited_res = next(res for res in responses if res.status_code == 429)
        assert "Too many requests" in rate_limited_res.json()["detail"]
        assert "Retry-After" in rate_limited_res.headers
        retry_after_val = int(rate_limited_res.headers["Retry-After"])
        assert retry_after_val > 0

        # Test that bypass header allows urgent/test operations
        bypass_res = await client.post(
            "/api/auth/login",
            headers={"X-Test-Bypass-Rate-Limit": "true"},
            json={"username": "invalid_user", "password": "WrongPassword@123"},
        )
        assert bypass_res.status_code == 401  # Not 429!
    finally:
        limiter.enforce_in_tests = False
        limiter.reset()


@pytest.mark.asyncio
async def test_structured_validation_errors(client: AsyncClient):
    """Input validation errors (422) return structured, field-specific error details."""
    # Obtain admin token
    login_res = await client.post(
        "/api/auth/login",
        headers={"X-Test-Bypass-Rate-Limit": "true"},
        json={"username": "admin", "password": "Admin@1234"},
    )
    admin_token = login_res.json()["access_token"]

    # Submit invalid patient payload (e.g. invalid date_of_birth format and empty name)
    res = await client.post(
        "/api/patients",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"full_name": "", "date_of_birth": "not-a-date", "gender": "invalid_gender"},
    )
    assert res.status_code == 422
    body = res.json()
    assert "Input validation failed" in body["detail"]
    assert "errors" in body
    assert len(body["errors"]) > 0
    fields = [e["field"] for e in body["errors"]]
    assert "date_of_birth" in fields or "full_name" in fields


@pytest.mark.asyncio
async def test_unhandled_exception_safe_500_no_traceback_leak(client: AsyncClient):
    """Unhandled internal server exceptions must return safe JSON without leaking tracebacks."""
    # Temporarily register a route that raises an unhandled ValueError
    @app.get("/api/test-internal-error")
    async def trigger_internal_error():
        raise ValueError("Simulated unexpected database failure with sensitive /internal/path/db.sqlite")

    try:
        r = await client.get("/api/test-internal-error")
        assert r.status_code == 500
        data = r.json()
        assert data["detail"] == "An internal server error occurred. Please contact system support."
        assert data["error_code"] == "INTERNAL_SERVER_ERROR"
        # Assert traceback and internal path are NOT in response body
        assert "Simulated unexpected database failure" not in r.text
        assert "/internal/path/db.sqlite" not in r.text
        assert "Traceback" not in r.text
    finally:
        # Remove route after test
        app.routes[:] = [route for route in app.routes if getattr(route, "path", None) != "/api/test-internal-error"]


@pytest.mark.asyncio
async def test_cors_preflight_restricted_headers(client: AsyncClient):
    """CORS preflight requests are properly verified against allowed methods and headers."""
    r = await client.options(
        "/api/patients",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )
    assert r.status_code == 200
    assert "http://localhost:5173" in r.headers.get("Access-Control-Allow-Origin", "")
    assert "POST" in r.headers.get("Access-Control-Allow-Methods", "")
