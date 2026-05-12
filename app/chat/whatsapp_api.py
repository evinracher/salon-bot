"""Meta WhatsApp Cloud API webhook (verification + inbound notifications)."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse, Response

from app.chat.whatsapp_queue import enqueue_whatsapp_inbound
from app.chat.whatsapp_schemas import extract_inbound_text_messages
from app.config import settings

logger = structlog.get_logger(__name__)

whatsapp_router = APIRouter(prefix="/webhooks", tags=["whatsapp"])


@whatsapp_router.get("/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
) -> PlainTextResponse:
    """Meta subscription verification (developer dashboard)."""
    if hub_mode != "subscribe":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid hub.mode",
        )
    if not settings.whatsapp_verify_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WHATSAPP_VERIFY_TOKEN is not configured",
        )
    if hub_verify_token != settings.whatsapp_verify_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid verify token",
        )
    if hub_challenge is None or hub_challenge == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing hub.challenge",
        )
    return PlainTextResponse(content=hub_challenge)


@whatsapp_router.post("/whatsapp")
async def receive_whatsapp_webhook(request: Request) -> Response:
    """
    Receive webhook events; enqueue inbound text messages and always ACK with 200.

    Meta retries on non-2xx; failures after enqueue should not trigger retries.
    """
    try:
        body = await request.json()
    except Exception:
        logger.warning("whatsapp_webhook_invalid_json")
        return Response(status_code=status.HTTP_200_OK)

    if not isinstance(body, dict):
        return Response(status_code=status.HTTP_200_OK)

    messages = extract_inbound_text_messages(body)
    for msg in messages:
        try:
            await enqueue_whatsapp_inbound(
                request.app,
                wa_id=msg.wa_id,
                text=msg.text,
                profile_name=msg.profile_name,
                message_id=msg.message_id,
            )
        except Exception:
            logger.exception(
                "whatsapp_webhook_enqueue_failed",
                wa_id=msg.wa_id,
                message_id=msg.message_id,
            )

    return Response(status_code=status.HTTP_200_OK)
