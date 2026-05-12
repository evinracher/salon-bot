"""BullMQ queue + worker for WhatsApp inbound processing."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable
from typing import Any, cast

import structlog
from bullmq import Queue, Worker
from fastapi import FastAPI

from app.chat.whatsapp_processor import bullmq_processor
from app.config import settings

logger = structlog.get_logger(__name__)

WHATSAPP_JOB_NAME = "whatsappInbound"


def _connection_opts() -> str | dict[str, object]:
    return settings.redis_url


async def start_whatsapp_worker(app: FastAPI) -> None:
    """Create BullMQ queue + worker when Redis is configured."""
    app.state.whatsapp_queue = None
    app.state.whatsapp_worker = None

    if not settings.redis_url.strip():
        logger.info("whatsapp_queue_disabled_no_redis_url")
        return

    conn = _connection_opts()
    queue_name = settings.whatsapp_queue_name

    queue = Queue(queue_name, conn)

    async def processor(job, token):
        await bullmq_processor(app, job, token)

    worker = Worker(
        queue_name,
        processor,
        {
            "connection": conn,
            "concurrency": settings.whatsapp_worker_concurrency,
        },
    )

    app.state.whatsapp_queue = queue
    app.state.whatsapp_worker = worker
    logger.info(
        "whatsapp_worker_started",
        queue=queue_name,
        concurrency=settings.whatsapp_worker_concurrency,
    )


async def shutdown_whatsapp(app: FastAPI) -> None:
    worker = getattr(app.state, "whatsapp_worker", None)
    queue = getattr(app.state, "whatsapp_queue", None)

    if worker is not None:
        await worker.close()
        app.state.whatsapp_worker = None

    if queue is not None:
        maybe_close = queue.close()
        if inspect.isawaitable(maybe_close):
            await cast(Awaitable[Any], maybe_close)
        app.state.whatsapp_queue = None

    logger.info("whatsapp_worker_shutdown")


async def enqueue_whatsapp_inbound(
    app: FastAPI,
    *,
    wa_id: str,
    text: str,
    profile_name: str | None,
    message_id: str,
) -> None:
    """Enqueue a single inbound message job."""
    queue = getattr(app.state, "whatsapp_queue", None)
    if queue is None:
        logger.warning(
            "whatsapp_enqueue_skipped_no_queue",
            wa_id=wa_id,
            message_id=message_id,
        )
        return

    payload = {
        "wa_id": wa_id,
        "text": text,
        "profile_name": profile_name,
        "message_id": message_id,
    }
    opts: dict[str, object] = {
        "attempts": settings.whatsapp_job_attempts,
        "removeOnComplete": True,
        "jobId": f"wa-{message_id}",
    }
    try:
        await queue.add(WHATSAPP_JOB_NAME, payload, opts)
    except Exception:
        logger.exception(
            "whatsapp_enqueue_failed",
            wa_id=wa_id,
            message_id=message_id,
        )
        raise
