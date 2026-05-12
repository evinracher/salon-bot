from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import Request
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.agent.protocols import CompiledSalonAgent
from app.chat.agent.prompts import salon_system_prompt
from app.chat.agent.runtime import current_session, pending_salon_state_patch
from app.chat.models.conversation import Conversation
from app.config import settings
from app.models.employee import Employee
from app.models.service import Service


def _thread_config(conversation_id: int) -> dict:
    return {
        "configurable": {"thread_id": str(conversation_id)},
        "recursion_limit": settings.chat_max_tool_iters,
    }


async def _checkpoint_preference_ids(
    graph: CompiledSalonAgent, config: dict
) -> tuple[Any, Any]:
    try:
        snap = await graph.aget_state(config)
    except Exception:
        return None, None
    values = getattr(snap, "values", None) or {}
    return values.get("preferred_service_id"), values.get("preferred_employee_id")


async def _preference_display_names(
    session: AsyncSession,
    preferred_service_id: Any,
    preferred_employee_id: Any,
) -> tuple[str | None, str | None]:
    service_name: str | None = None
    employee_name: str | None = None
    if isinstance(preferred_service_id, int):
        service_row = await session.get(Service, preferred_service_id)
        if service_row is not None:
            service_name = service_row.name
    if isinstance(preferred_employee_id, int):
        employee_row = await session.get(Employee, preferred_employee_id)
        if employee_row is not None:
            employee_name = employee_row.name
    return service_name, employee_name


async def run_turn(
    graph: CompiledSalonAgent,
    conversation: Conversation,
    content: str,
    session: AsyncSession,
) -> str:
    config = _thread_config(conversation.id)
    pref_sid, pref_eid = await _checkpoint_preference_ids(graph, config)
    svc_name, emp_name = await _preference_display_names(session, pref_sid, pref_eid)
    now_local = datetime.now(ZoneInfo(settings.timezone))
    system_text = salon_system_prompt(
        conversation.customer_id,
        preferred_service_name=svc_name,
        preferred_employee_name=emp_name,
        current_local_datetime=now_local.isoformat(timespec="seconds"),
    )

    patch_bag: dict[str, Any] = {}
    session_token = current_session.set(session)
    patch_token = pending_salon_state_patch.set(patch_bag)
    try:
        result = await graph.ainvoke(
            {
                "messages": [
                    SystemMessage(content=system_text),
                    HumanMessage(content=content),
                ],
            },
            config=config,
        )
    finally:
        try:
            if patch_bag:
                await graph.aupdate_state(config=config, values=patch_bag)
        finally:
            pending_salon_state_patch.reset(patch_token)
            current_session.reset(session_token)

    messages = result.get("messages", [])
    for message in reversed(messages):
        if isinstance(message, AIMessage) and isinstance(message.content, str):
            return message.content
    return ""


async def inject_manual_ai_message(
    graph: CompiledSalonAgent,
    request: Request,
    conversation_id: int,
    content: str,
) -> None:
    _ = request
    await graph.aupdate_state(
        config=_thread_config(conversation_id),
        values={"messages": [AIMessage(content=content)]},
    )
