from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _alembic_upgrade() -> None:
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(autouse=True)
async def _truncate_tables() -> AsyncIterator[None]:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE employees, services, employee_services, appointments, "
                "messages, conversations "
                "RESTART IDENTITY CASCADE",
            ),
        )
    yield
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE employees, services, employee_services, appointments, "
                "messages, conversations "
                "RESTART IDENTITY CASCADE",
            ),
        )


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
