"""Outbound WhatsApp Cloud API (Meta Graph) calls."""

from __future__ import annotations

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)


async def send_whatsapp_text_message(*, to_wa_id: str, text: str) -> None:
    """
    Send a plain text message to a WhatsApp user.

    ``to_wa_id`` must be the user's WhatsApp ID (digits only), as returned by Meta webhooks.
    """
    if not settings.whatsapp_access_token or not settings.whatsapp_phone_number_id:
        msg = "WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID must be set to send messages"
        logger.error("whatsapp_send_missing_config")
        raise RuntimeError(msg)

    url = (
        f"https://graph.facebook.com/{settings.whatsapp_graph_api_version}/"
        f"{settings.whatsapp_phone_number_id}/messages"
    )
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to_wa_id,
        "type": "text",
        "text": {"preview_url": False, "body": text},
    }
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload, headers=headers)

    if resp.status_code >= 400:
        logger.warning(
            "whatsapp_send_failed",
            status_code=resp.status_code,
            body=resp.text[:500],
        )
        resp.raise_for_status()
