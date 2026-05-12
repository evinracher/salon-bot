from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.appointments import router as appointments_router
from app.api.availability import router as availability_router
from app.api.employee_services import router as employee_services_router
from app.api.employees import router as employees_router
from app.api.services import router as services_router
from app.chat.bootstrap import chat_lifespan, register_chat_routers
from app.db import engine
from app.logging import RequestContextMiddleware, configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    async with chat_lifespan(app):
        yield
    await engine.dispose()


app = FastAPI(title="salon-bot", lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
# Wildcard origin: credentials must be false (CORS spec). Use per-origin + credentials in prod.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(employees_router)
app.include_router(services_router)
app.include_router(employee_services_router)
app.include_router(appointments_router)
app.include_router(availability_router)
register_chat_routers(app)
