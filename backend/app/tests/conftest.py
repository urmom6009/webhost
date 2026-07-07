import os
import atexit

os.environ["PUBLIC_BASE_URL"] = "https://store.test"
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi"
os.environ["TELEGRAM_WEBHOOK_SECRET"] = "test_webhook_secret_32_bytes"
os.environ["TELEGRAM_BOT_USERNAME"] = "StorefrontTestBot"
os.environ["STRIPE_SECRET_KEY"] = "sk_test_valid_for_unit_tests"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_valid_for_unit_tests"
os.environ["POSTGRES_PASSWORD"] = "unit_test_postgres_password"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DELIVERY_TOKEN_TTL_MINUTES"] = "60"
os.environ["DELIVERY_TOKEN_MAX_USES"] = "3"
os.environ["ADMIN_TELEGRAM_IDS"] = "9001"
os.environ["ADMIN_PORTAL_TOKEN"] = "unit-test-admin-token"

_postgres_container = None

if os.getenv("USE_TESTCONTAINERS") == "1":
    from testcontainers.postgres import PostgresContainer

    _postgres_container = PostgresContainer("postgres:16-alpine")
    _postgres_container.start()
    atexit.register(_postgres_container.stop)
    os.environ["DATABASE_URL"] = _postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://",
        "postgresql+asyncpg://",
        1,
    )

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base


@pytest_asyncio.fixture
async def session():
    engine = create_async_engine(os.environ["DATABASE_URL"])
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        yield db

    await engine.dispose()
