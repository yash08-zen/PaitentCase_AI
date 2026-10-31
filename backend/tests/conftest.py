"""
tests/conftest.py
-----------------
Pytest configuration and shared async fixtures for test suite.
"""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["APP_SECRET_KEY"] = "test-secret-key-for-unit-tests"
os.environ["UPLOAD_DIR"] = "./test_uploads"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["AUTO_ANALYSIS_ENABLED"] = "false"  # tests that need it switch it on explicitly

from app.main import app, seed_questions, ensure_default_admin
from app.database import engine
from app.models import Base


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    """Setup clean tables and seed default users before each test."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_questions()
    await ensure_default_admin()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    """Provide AsyncClient for test requests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_headers(client):
    """Return Authorization headers for the default admin account."""
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "Admin@1234"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def reset_mock_llm():
    """Each test starts with a clean mock LLM (no overrides, available)."""
    from app.services.llm.manager import llm_service
    llm_service.mock.reset()
    yield
    llm_service.mock.reset()
