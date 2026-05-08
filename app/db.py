from collections.abc import AsyncIterator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from fastapi import Request

from app.config import settings


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        },
    )


def asyncpg_connect_args(url: str) -> dict[str, bool]:
    """Local Docker Postgres: disable SSL. Remote (e.g. Neon): leave default."""
    if "127.0.0.1" in url or "localhost" in url:
        return {"ssl": False}
    return {}


_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None


def init_db_runtime(
    database_url: str | None = None,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    global _engine, _async_session_maker
    if _engine is not None and _async_session_maker is not None:
        return _engine, _async_session_maker

    url = database_url or settings.database_url
    _engine = create_async_engine(
        url,
        echo=False,
        connect_args=asyncpg_connect_args(url),
    )
    _async_session_maker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine, _async_session_maker


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database engine is not initialized")
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    if _async_session_maker is None:
        raise RuntimeError("Database session maker is not initialized")
    return _async_session_maker


async def dispose_db_runtime() -> None:
    global _engine, _async_session_maker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _async_session_maker = None


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    session_maker = (
        getattr(request.app.state, "db_session_maker", None) or get_session_maker()
    )
    async with session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
