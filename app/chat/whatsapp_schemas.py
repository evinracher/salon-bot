"""Parse Meta WhatsApp Cloud API webhook payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InboundTextMessage:
    """Single inbound user text message from a webhook notification."""

    wa_id: str
    """Sender WhatsApp ID (digits, no +)."""
    profile_name: str | None
    text: str
    message_id: str


def normalize_customer_phone(wa_id: str) -> str:
    """Map WhatsApp wa_id to the phone string stored on Customer.phone."""
    digits = "".join(c for c in wa_id if c.isdigit())
    if not digits:
        return wa_id.strip()
    return f"+{digits}"


def extract_inbound_text_messages(body: dict[str, Any]) -> list[InboundTextMessage]:
    """
    Extract inbound user text messages from a Meta webhook POST body.

    Ignores status updates, non-text types, and malformed fragments.
    """
    out: list[InboundTextMessage] = []
    if body.get("object") != "whatsapp_business_account":
        return out

    contacts_by_wa: dict[str, str | None] = {}
    for entry in body.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for c in value.get("contacts") or []:
                wa = c.get("wa_id")
                if isinstance(wa, str) and wa:
                    profile = (
                        (c.get("profile") or {})
                        if isinstance(c.get("profile"), dict)
                        else {}
                    )
                    name = profile.get("name")
                    contacts_by_wa[wa] = name if isinstance(name, str) else None

            for msg in value.get("messages") or []:
                if not isinstance(msg, dict):
                    continue
                if msg.get("type") != "text":
                    continue
                text_obj = msg.get("text")
                if not isinstance(text_obj, dict):
                    continue
                body_text = text_obj.get("body")
                if not isinstance(body_text, str) or not body_text.strip():
                    continue
                wa_from = msg.get("from")
                msg_id = msg.get("id")
                if not isinstance(wa_from, str) or not isinstance(msg_id, str):
                    continue
                profile_name = contacts_by_wa.get(wa_from)
                out.append(
                    InboundTextMessage(
                        wa_id=wa_from,
                        profile_name=profile_name,
                        text=body_text,
                        message_id=msg_id,
                    ),
                )
    return out
