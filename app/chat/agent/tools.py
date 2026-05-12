import json
from datetime import date, datetime, timedelta

from langchain_core.tools import tool
from sqlalchemy import select

from app.chat.agent.runtime import current_session
from app.models.appointment import Appointment
from app.models.employee import Employee
from app.models.employee_service import EmployeeService
from app.models.service import Service
from app.schemas.appointment import AppointmentStatus
from app.services.availability import (
    build_business_window,
    generate_candidate_slots,
    has_overlap,
)
from app.services.datetime_utils import normalize_to_second_in_timezone


def _get_session():
    session = current_session.get()
    if session is None:
        msg = "Chat session context is not initialized"
        raise RuntimeError(msg)
    return session


def _as_tool_str(payload: object) -> str:
    """Groq requires tool message content as a string (JSON text)."""
    return json.dumps(payload, default=str)


@tool
async def list_employees() -> str:
    """List all employees."""
    session = _get_session()
    rows = list((await session.scalars(select(Employee).order_by(Employee.id))).all())
    payload = [{"id": row.id, "name": row.name, "phone": row.phone} for row in rows]
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
async def check_availability(employee_id: int, date_value: str) -> str:
    """List available slots for an employee on a date (YYYY-MM-DD)."""
    session = _get_session()
    target_date = date.fromisoformat(date_value)
    relations = await session.execute(
        select(EmployeeService.service_id).where(
            EmployeeService.employee_id == employee_id
        )
    )
    service_ids = [row[0] for row in relations.all()]
    if not service_ids:
        return _as_tool_str([])

    service_durations = {
        row.id: row.duration_minutes
        for row in (
            await session.scalars(select(Service).where(Service.id.in_(service_ids)))
        ).all()
    }
    if not service_durations:
        return _as_tool_str([])

    min_duration = min(service_durations.values())
    from app.config import settings

    window = build_business_window(
        target_date=target_date,
        timezone_name=settings.timezone,
        open_time=settings.business_open_time,
        close_time=settings.business_close_time,
        business_days=settings.business_weekdays,
    )
    if window is None:
        return _as_tool_str([])
    open_dt, close_dt = window
    candidate_slots = generate_candidate_slots(
        open_dt=open_dt,
        close_dt=close_dt,
        slot_interval_minutes=settings.slot_interval_minutes,
        service_duration_minutes=min_duration,
    )
    if not candidate_slots:
        return _as_tool_str([])

    result = await session.execute(
        select(Appointment.start_time, Appointment.end_time).where(
            Appointment.employee_id == employee_id,
            Appointment.status != AppointmentStatus.CANCELLED.value,
            Appointment.start_time < close_dt,
            Appointment.end_time > open_dt,
        )
    )
    appointments = [
        (
            normalize_to_second_in_timezone(start, settings.timezone),
            normalize_to_second_in_timezone(end, settings.timezone),
        )
        for start, end in result.all()
    ]
    payload = [
        {"start": start.isoformat(), "end": end.isoformat()}
        for start, end in candidate_slots
        if not has_overlap(start=start, end=end, appointments=appointments)
    ]
    return _as_tool_str(payload)


@tool
async def book_appointment(
    customer_id: int,
    employee_id: int,
    service_id: int,
    start_time: str,
) -> str:
    """Create a scheduled appointment for a customer."""
    session = _get_session()
    start = datetime.fromisoformat(start_time)
    service = await session.get(Service, service_id)
    if service is None:
        raise ValueError("Service not found")
    end = start + timedelta(minutes=service.duration_minutes)
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
    book_appointment,
    cancel_appointment,
]
