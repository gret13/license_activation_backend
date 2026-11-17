import os
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from pydantic import SecretStr
from redis.asyncio import Redis
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings
from app.db.models import Base, License
from app.domain.licensing import license_hash


@pytest.fixture
def test_license_key() -> str:
    return "Ds23-Da34-We21-E334"


@pytest.fixture
def test_database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")
    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("Test database name must end with _test")
    return url


@pytest.fixture
def test_redis_url() -> str:
    url = os.getenv("TEST_REDIS_URL")
    if not url:
        pytest.skip("TEST_REDIS_URL is not configured")
    return url


@pytest_asyncio.fixture
async def db_engine(test_database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(test_database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
def db_sessions(db_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def seeded_sessions(
    db_sessions: async_sessionmaker[AsyncSession],
    test_license_key: str,
) -> async_sessionmaker[AsyncSession]:
    async with db_sessions() as session:
        async with session.begin():
            session.add(
                License(
                    license_key=test_license_key,
                    license_hash=license_hash(test_license_key),
                )
            )
    return db_sessions


@pytest.fixture
def test_settings(test_database_url: str, test_redis_url: str) -> Settings:
    return Settings(
        database_url=test_database_url,
        redis_url=test_redis_url,
        log_hmac_secret=SecretStr("test-only-logging-secret-1234567890-abcdef"),
        app_env="production",
    )


@pytest_asyncio.fixture
async def redis_client(test_redis_url: str) -> AsyncIterator[Redis]:
    client = Redis.from_url(test_redis_url)
    try:
        yield client
    finally:
        await client.aclose()


@pytest_asyncio.fixture
async def api_client(
    test_settings: Settings,
    redis_client: Redis,
    seeded_sessions: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setenv("DATABASE_URL", test_settings.database_url)
    monkeypatch.setenv("REDIS_URL", test_settings.redis_url)
    monkeypatch.setenv(
        "LOG_HMAC_SECRET", test_settings.log_hmac_secret.get_secret_value()
    )
    monkeypatch.chdir(tmp_path)

    from app.main import create_app

    api = create_app(test_settings)
    transport = httpx.ASGITransport(app=api, client=("192.0.2.10", 55000))
    async with api.router.lifespan_context(api):
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client
