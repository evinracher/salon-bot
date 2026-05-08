from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from contextlib import AsyncExitStack

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.api.appointments import router as appointments_router
from app.api.availability import router as availability_router
from app.api.employee_services import router as employee_services_router
from app.api.employees import router as employees_router
from app.api.services import router as services_router
from app.chat.api import router as chat_router
from app.chat.agent.graph import graph_with_checkpointer
from app.config import settings
from app.db import dispose_db_runtime, init_db_runtime
from app.logging import RequestContextMiddleware, configure_logging

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    db_engine, db_session_maker = init_db_runtime(settings.database_url)
    app.state.db_engine = db_engine
    app.state.db_session_maker = db_session_maker
    app.state.chat_graph = None
    app.state.chat_checkpointer = None
    app.state.chat_available = False
    app.state.chat_init_error = None

    async with AsyncExitStack() as stack:
        try:
            chat_graph, chat_checkpointer = await stack.enter_async_context(
                graph_with_checkpointer()
            )
            app.state.chat_graph = chat_graph
            app.state.chat_checkpointer = chat_checkpointer
            app.state.chat_available = True
        except Exception:
            logger.exception("chat_runtime_init_failed")
            app.state.chat_available = False
            app.state.chat_init_error = "chat runtime initialization failed"
        try:
            yield
        finally:
            app.state.chat_graph = None
            app.state.chat_checkpointer = None
            app.state.chat_available = False
            await dispose_db_runtime()


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
