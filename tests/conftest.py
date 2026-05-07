from collections.abc import AsyncIterator
from pathlib import Path
import os

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

_db_user = os.getenv("DB_USER", "user")
_db_password = os.getenv("DB_PASSWORD", "password")
_db_host = os.getenv("DB_HOST", "127.0.0.1")
_db_port = os.getenv("DB_PORT", "5433")
_test_db_name = os.getenv("TEST_DB_NAME", "salon_bot_test")
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    f"postgresql+asyncpg://{_db_user}:{_db_password}@{_db_host}:{_db_port}/{_test_db_name}",
)

from app.config import settings  # noqa: E402
from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402

assert "test" in settings.database_url, "refusing to run tests against non-test DB"


@pytest.fixture(scope="session", autouse=True)
def _alembic_upgrade() -> None:
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(autouse=True)
async def _truncate_employees() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE employees RESTART IDENTITY CASCADE"))
    yield
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE employees RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
