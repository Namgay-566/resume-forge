import asyncio
import os
from collections.abc import AsyncIterator

# Test settings must be in place before the app (and its cached settings) is imported.
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-at-least-32-characters")
os.environ["COOKIE_SECURE"] = "false"
# Whatever a developer's .env says, tests run jobs inline with in-memory rate limits.
os.environ["ENVIRONMENT"] = "test"
os.environ["JOB_QUEUE"] = "inline"
os.environ["RATE_LIMIT_STORAGE_URI"] = "memory://"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.models  # noqa: F401  (register all tables)
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_session, get_session_factory
from app.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    make_url(get_settings().database_url)
    .set(database="resumeforge_test")
    .render_as_string(hide_password=False),
)


async def _prepare_database() -> None:
    url = make_url(TEST_DATABASE_URL)
    admin = create_async_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    await admin.dispose()

    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


@pytest.fixture(scope="session")
def _database() -> None:
    asyncio.run(_prepare_database())


@pytest.fixture
async def db_session(_database: None) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    async with engine.begin() as conn:
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {tables} CASCADE"))
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = override_session
    # Background tasks open their own sessions; point them at the test database too.
    test_maker = async_sessionmaker(db_session.bind, expire_on_commit=False)
    app.dependency_overrides[get_session_factory] = lambda: test_maker
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> None:
    """Rate-limit counters are process-wide; start every test with a clean slate."""
    from app.ai.rate_limit import limiter

    limiter.reset()


@pytest.fixture(autouse=True)
def _clear_inference_cache() -> None:
    from app.services.skill_gap.service import inference_cache

    inference_cache.clear()
