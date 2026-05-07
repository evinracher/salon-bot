from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.employees import router as employees_router
from app.db import engine
from app.logging import RequestContextMiddleware, configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield
    await engine.dispose()


app = FastAPI(title="salon-bot", lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
app.include_router(employees_router)
