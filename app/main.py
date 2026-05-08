from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from app.api.appointments import router as appointments_router
from app.api.availability import router as availability_router
from app.api.employee_services import router as employee_services_router
from app.api.employees import router as employees_router
from app.api.services import router as services_router
from app.chat.api import router as chat_router
from app.chat.agent.graph import graph_with_checkpointer
from app.config import settings
from app.db import engine
from app.logging import RequestContextMiddleware, configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    async with graph_with_checkpointer() as (chat_graph, chat_checkpointer):
        app.state.chat_graph = chat_graph
        app.state.chat_checkpointer = chat_checkpointer
        yield
    app.state.chat_graph = None
    app.state.chat_checkpointer = None
    await engine.dispose()


app = FastAPI(title="salon-bot", lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
allowed_origins = [
    origin.strip()
    for origin in settings.cors_allowed_origins.split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.options("/{path:path}", include_in_schema=False)
async def options_handler(path: str) -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


app.include_router(employees_router)
app.include_router(services_router)
app.include_router(employee_services_router)
app.include_router(appointments_router)
app.include_router(availability_router)
app.include_router(chat_router)
