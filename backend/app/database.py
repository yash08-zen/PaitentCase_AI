"""
database.py
-----------
Async SQLAlchemy engine and session factory backed by SQLite (aiosqlite).
Designed so the DATABASE_URL can be swapped to PostgreSQL later by changing
only the Settings value — all other code remains the same.
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=(settings.APP_ENV == "development"),
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """All ORM models inherit from this class."""
    pass


async def get_db():
    """FastAPI dependency that yields an async DB session and closes it after the request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


from sqlalchemy import text

async def init_db():
    """Create all tables and ensure schema migrations. Called at application startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # SQLite schema auto-migration for encounters
        res = await conn.execute(text("PRAGMA table_info(encounters)"))
        existing_enc_cols = {row[1] for row in res.fetchall()}
        if existing_enc_cols:
            if "doctor_notes" not in existing_enc_cols:
                await conn.execute(text("ALTER TABLE encounters ADD COLUMN doctor_notes TEXT"))
            if "reviewed_at" not in existing_enc_cols:
                await conn.execute(text("ALTER TABLE encounters ADD COLUMN reviewed_at TIMESTAMP"))
            if "reviewed_by" not in existing_enc_cols:
                await conn.execute(text("ALTER TABLE encounters ADD COLUMN reviewed_by INTEGER"))

        # SQLite schema auto-migration for case_summaries
        res_cs = await conn.execute(text("PRAGMA table_info(case_summaries)"))
        existing_cs_cols = {row[1] for row in res_cs.fetchall()}
        if existing_cs_cols:
            if "doctor_notes" not in existing_cs_cols:
                await conn.execute(text("ALTER TABLE case_summaries ADD COLUMN doctor_notes TEXT"))
            if "reviewed_at" not in existing_cs_cols:
                await conn.execute(text("ALTER TABLE case_summaries ADD COLUMN reviewed_at TIMESTAMP"))
            if "reviewed_by" not in existing_cs_cols:
                await conn.execute(text("ALTER TABLE case_summaries ADD COLUMN reviewed_by INTEGER"))

        # SQLite schema auto-migration for conflicts
        res_conf = await conn.execute(text("PRAGMA table_info(conflicts)"))
        existing_conf_cols = {row[1] for row in res_conf.fetchall()}
        if existing_conf_cols:
            if "rule_id" not in existing_conf_cols:
                await conn.execute(text("ALTER TABLE conflicts ADD COLUMN rule_id TEXT"))
            if "resolution_note" not in existing_conf_cols:
                await conn.execute(text("ALTER TABLE conflicts ADD COLUMN resolution_note TEXT"))
            if "resolved_by" not in existing_conf_cols:
                await conn.execute(text("ALTER TABLE conflicts ADD COLUMN resolved_by INTEGER"))
            if "resolved_at" not in existing_conf_cols:
                await conn.execute(text("ALTER TABLE conflicts ADD COLUMN resolved_at TIMESTAMP"))
