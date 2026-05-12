import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from langchain_core.tools import tool
from sqlalchemy import select

from app.chat.agent.runtime import current_session, merge_salon_state_patch
from app.config import settings
from app.models.appointment import Appointment
from app.models.customer import Customer
from app.models.employee import Employee
from app.models.employee_service import EmployeeService
from app.models.service import Service
from app.schemas.appointment import AppointmentStatus
from app.schemas.availability import AvailabilitySlot
from app.services.datetime_utils import (
    ensure_aware_in_timezone,
    is_future_in_reference_tz,
    is_slot_boundary_in_timezone,
    is_slot_duration_aligned,
)
from app.services.salon_availability import (
    compute_availability_slots,
    resolve_service_duration_minutes,
)


def _get_session():
    session = current_session.get()
    if session is None:
        msg = "Chat session context is not initialized"
        raise RuntimeError(msg)
    return session


def _as_tool_str(payload: object) -> str:
    """Groq requires tool message content as a string (JSON text)."""
    return json.dumps(payload, default=str)


def _group_slots_by_daypart(
    slots: list[AvailabilitySlot],
    employee_names: dict[int, str],
    *,
    max_per_block: int = 6,
) -> dict[str, Any]:
    tz = ZoneInfo(settings.timezone)
    blocks: dict[str, list[dict[str, Any]]] = {
        "morning": [],
        "afternoon": [],
        "evening": [],
    }
    for slot in slots:
        local = slot.start.astimezone(tz)
        hour = local.hour
        if hour < 12:
            key = "morning"
        elif hour < 17:
            key = "afternoon"
        else:
            key = "evening"
        if len(blocks[key]) >= max_per_block:
            continue
        blocks[key].append(
            {
                "time_local": local.strftime("%H:%M"),
                "start": slot.start.isoformat(),
                "end": slot.end.isoformat(),
                "available_employees": [
                    {"id": eid, "name": employee_names.get(eid, "Unknown")}
                    for eid in slot.employee_ids
                ],
            }
        )
    shown = sum(len(v) for v in blocks.values())
    return {
        "daypart_labels": {
            "morning": "Mañana",
            "afternoon": "Tarde",
            "evening": "Noche",
        },
        "slots_by_daypart": blocks,
        "truncated": shown < len(slots),
        "total_slots": len(slots),
        "shown_slots": shown,
    }


async def _booking_has_overlap(
    session,
    employee_id: int,
    start_time: datetime,
    end_time: datetime,
) -> bool:
    stmt = select(Appointment.id).where(
        Appointment.employee_id == employee_id,
        Appointment.status != AppointmentStatus.CANCELLED.value,
        Appointment.start_time < end_time,
        Appointment.end_time > start_time,
    )
    return (await session.scalar(stmt.limit(1))) is not None


@tool
async def list_employees() -> str:
    """List all employees and which services each can perform."""
    session = _get_session()
    employees = list(
        (await session.scalars(select(Employee).order_by(Employee.id))).all()
    )
    rows = (
        await session.execute(
            select(EmployeeService.employee_id, Service.id, Service.name)
            .join(Service, Service.id == EmployeeService.service_id)
            .order_by(EmployeeService.employee_id, Service.id)
        )
    ).all()
    by_employee: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for employee_id, service_id, service_name in rows:
        by_employee[employee_id].append(
            {"id": service_id, "name": service_name},
        )
    payload = [
        {
            "id": row.id,
            "name": row.name,
            "phone": row.phone,
            "services": by_employee.get(row.id, []),
        }
        for row in employees
    ]
    return _as_tool_str(payload)


@tool
async def list_services() -> str:
    """List all services."""
    session = _get_session()
    rows = list((await session.scalars(select(Service).order_by(Service.id))).all())
    payload = [
        {
            "id": row.id,
            "name": row.name,
            "duration_minutes": row.duration_minutes,
            "price": str(row.price),
        }
        for row in rows
    ]
    return _as_tool_str(payload)


@tool
async def check_availability(
    service_id: int,
    date_value: str,
    employee_id: int | None = None,
) -> str:
    """List availability for a service on a date (YYYY-MM-DD), grouped by morning/afternoon/evening."""
    session = _get_session()
    target_date = date.fromisoformat(date_value)
    now_local = datetime.now(ZoneInfo(settings.timezone))
    if target_date < now_local.date():
        return _as_tool_str(
            {
                "error": "date_must_be_today_or_future",
                "timezone": settings.timezone,
                "today": now_local.date().isoformat(),
            }
        )
    service, duration = await resolve_service_duration_minutes(
        session, service_id=service_id, duration_minutes=None
    )
    if service is None:
        return _as_tool_str({"error": "service_not_found"})

    if duration <= 0 or duration % settings.slot_interval_minutes != 0:
        return _as_tool_str({"error": "duration_not_aligned_to_slot_interval"})

    if employee_id is not None:
        employee = await session.get(Employee, employee_id)
        if employee is None:
            return _as_tool_str({"error": "employee_not_found"})
        link = await session.scalar(
            select(EmployeeService.id).where(
                EmployeeService.employee_id == employee_id,
                EmployeeService.service_id == service_id,
            )
        )
        if link is None:
            return _as_tool_str({"error": "employee_does_not_perform_service"})

    slots = await compute_availability_slots(
        session,
        service_id=service_id,
        date_value=target_date,
        employee_id=employee_id,
        selected_duration_minutes=duration,
    )
    if target_date == now_local.date():
        slots = [slot for slot in slots if slot.start > now_local]

    employee_ids: set[int] = set()
    for slot in slots:
        employee_ids.update(slot.employee_ids)
    id_list = sorted(employee_ids)
    names: dict[int, str] = {}
    if id_list:
        for emp in (
            await session.scalars(select(Employee).where(Employee.id.in_(id_list)))
        ).all():
            names[emp.id] = emp.name

    payload: dict[str, Any] = {
        "service": {"id": service.id, "name": service.name},
        "date": date_value,
        "timezone": settings.timezone,
        "service_duration_minutes": duration,
        "grouped": _group_slots_by_daypart(slots, names),
    }
    if employee_id is not None:
        emp = await session.get(Employee, employee_id)
        payload["scoped_employee"] = (
            {"id": employee_id, "name": emp.name} if emp is not None else None
        )
    return _as_tool_str(payload)


@tool
async def set_preferred_service(service_id: int | None = None) -> str:
    """Set or clear the preferred service for this conversation (checkpoint state)."""
    session = _get_session()
    if service_id is not None:
        row = await session.get(Service, service_id)
        if row is None:
            raise ValueError("Service not found")
    merge_salon_state_patch(preferred_service_id=service_id)
    return _as_tool_str({"preferred_service_id": service_id})


@tool
async def set_preferred_employee(employee_id: int | None = None) -> str:
    """Set or clear the preferred stylist for this conversation (checkpoint state)."""
    session = _get_session()
    if employee_id is not None:
        row = await session.get(Employee, employee_id)
        if row is None:
            raise ValueError("Employee not found")
    merge_salon_state_patch(preferred_employee_id=employee_id)
    return _as_tool_str({"preferred_employee_id": employee_id})


@tool
async def book_appointment(
    customer_id: int,
    employee_id: int,
    service_id: int,
    start_time: str,
) -> str:
    """Create a scheduled appointment for a customer."""
    session = _get_session()
    customer = await session.get(Customer, customer_id)
    if customer is None:
        raise ValueError("Customer not found")
    employee = await session.get(Employee, employee_id)
    if employee is None:
        raise ValueError("Employee not found")
    service = await session.get(Service, service_id)
    if service is None:
        raise ValueError("Service not found")

    link = await session.scalar(
        select(EmployeeService.id).where(
            EmployeeService.employee_id == employee_id,
            EmployeeService.service_id == service_id,
        )
    )
    if link is None:
        raise ValueError("Employee does not perform this service")

    start = datetime.fromisoformat(start_time)
    start = ensure_aware_in_timezone(start, settings.timezone)
    end = start + timedelta(minutes=service.duration_minutes)
    if end <= start:
        raise ValueError("end_time must be after start_time")

    interval = settings.slot_interval_minutes
    aligned_start = is_slot_boundary_in_timezone(
        value=start,
        interval_minutes=interval,
        timezone_name=settings.timezone,
    )
    aligned_end = is_slot_boundary_in_timezone(
        value=end,
        interval_minutes=interval,
        timezone_name=settings.timezone,
    )
    aligned_duration = is_slot_duration_aligned(
        start=start,
        end=end,
        interval_minutes=interval,
    )
    if not (aligned_start and aligned_end and aligned_duration):
        raise ValueError(
            f"Appointment times must align to slot interval ({interval} minutes) "
            f"in {settings.timezone}",
        )
    if not is_future_in_reference_tz(start, reference_timezone_name=settings.timezone):
        raise ValueError("start_time must be in the future")

    if await _booking_has_overlap(session, employee_id, start, end):
        raise ValueError("Appointment overlaps existing booking for this employee")

    appointment = Appointment(
        customer_id=customer_id,
        employee_id=employee_id,
        service_id=service_id,
        start_time=start,
        end_time=end,
        status=AppointmentStatus.SCHEDULED.value,
    )
    session.add(appointment)
    await session.commit()
    await session.refresh(appointment)

    merge_salon_state_patch(
        preferred_service_id=service_id,
        preferred_employee_id=employee_id,
    )

    return _as_tool_str(
        {
            "appointment_id": appointment.id,
            "start_time": appointment.start_time.isoformat(),
            "end_time": appointment.end_time.isoformat(),
            "status": appointment.status,
        }
    )


@tool
async def cancel_appointment(appointment_id: int) -> str:
    """Cancel an appointment by id."""
    session = _get_session()
    appointment = await session.get(Appointment, appointment_id)
    if appointment is None:
        raise ValueError("Appointment not found")
    appointment.status = AppointmentStatus.CANCELLED.value
    await session.commit()
    await session.refresh(appointment)
    return _as_tool_str(
        {"appointment_id": appointment.id, "status": appointment.status}
    )


ALL_TOOLS = [
    list_employees,
    list_services,
    check_availability,
    set_preferred_service,
    set_preferred_employee,
    book_appointment,
    cancel_appointment,
]
