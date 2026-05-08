from datetime import date, datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import tool
from sqlalchemy import select

from app.chat.agent.runtime import (
    current_booking_confirmed,
    current_phone,
    current_session,
)
from app.chat.service import set_bot_enabled
from app.models.employee import Employee
from app.models.employee_service import EmployeeService
from app.models.service import Service
from app.config import settings
from app.schemas.appointment import AppointmentCreate, AppointmentStatus
from app.services.appointments import (
    create_appointment as create_appointment_svc,
    list_appointments_by_phone,
)
from app.services.availability_service import compute_availability


def _ctx() -> tuple:
    session = current_session.get()
    phone = current_phone.get()
    if session is None or phone is None:
        raise RuntimeError("Chat tool context is not initialized")
    return session, phone


@tool
async def list_services() -> list[dict]:
    """List available salon services with id, name, duration, and price."""
    session, _ = _ctx()
    result = await session.scalars(select(Service).order_by(Service.id))
    return [
        {
            "id": svc.id,
            "name": svc.name,
            "duration_minutes": svc.duration_minutes,
            "price": str(svc.price),
        }
        for svc in result.all()
    ]


@tool
async def list_employees(service_id: int | None = None) -> list[dict]:
    """List employees; optionally filter by service id."""
    session, _ = _ctx()
    stmt = select(Employee)
    if service_id is not None:
        stmt = stmt.join(
            EmployeeService, EmployeeService.employee_id == Employee.id
        ).where(EmployeeService.service_id == service_id)
    result = await session.scalars(stmt.order_by(Employee.id))
    return [
        {"id": emp.id, "name": emp.name, "phone": emp.phone} for emp in result.all()
    ]


@tool
async def get_availability(
    service_id: int, date_iso: str, employee_id: int | None = None
) -> dict:
    """Get availability for a service and date (YYYY-MM-DD)."""
    session, _ = _ctx()
    availability = await compute_availability(
        session,
        service_id=service_id,
        date_value=date.fromisoformat(date_iso),
        employee_id=employee_id,
    )
    return availability.model_dump(mode="json")


@tool
async def create_appointment(
    employee_id: int,
    service_id: int,
    client_name: str,
    start_time_iso: str,
    end_time_iso: str,
) -> dict:
    """Create an appointment for current customer phone."""
    if not current_booking_confirmed.get():
        raise RuntimeError(
            "Booking not confirmed yet. Ask user for explicit confirmation first."
        )
    session, phone = _ctx()
    payload = AppointmentCreate(
        employee_id=employee_id,
        service_id=service_id,
        client_name=client_name,
        client_phone=phone,
        start_time=datetime.fromisoformat(start_time_iso),
        end_time=datetime.fromisoformat(end_time_iso),
        status=AppointmentStatus.SCHEDULED,
    )
    appointment = await create_appointment_svc(session, payload)
    return {
        "id": appointment.id,
        "employee_id": appointment.employee_id,
        "service_id": appointment.service_id,
        "client_name": appointment.client_name,
        "client_phone": appointment.client_phone,
        "start_time": appointment.start_time.isoformat(),
        "end_time": appointment.end_time.isoformat(),
        "status": appointment.status,
    }


@tool
async def list_my_appointments() -> list[dict]:
    """List appointments for the current customer phone."""
    session, phone = _ctx()
    rows = await list_appointments_by_phone(session, phone=phone)
    return [
        {
            "id": appt.id,
            "employee_id": appt.employee_id,
            "service_id": appt.service_id,
            "start_time": appt.start_time.isoformat(),
            "end_time": appt.end_time.isoformat(),
            "status": appt.status,
        }
        for appt in rows
    ]


@tool
async def request_human_handoff(reason: str) -> dict:
    """Disable bot and request manager follow-up."""
    session, phone = _ctx()
    conversation = await set_bot_enabled(session, phone=phone, enabled=False)
    return {
        "ok": True,
        "reason": reason,
        "phone": conversation.phone,
        "bot_enabled": conversation.bot_enabled,
    }


@tool
def now_in_salon_tz() -> str:
    """Get current local datetime in salon timezone."""
    return datetime.now(ZoneInfo(settings.timezone)).isoformat()


ALL_TOOLS = [
    list_services,
    list_employees,
    get_availability,
    create_appointment,
    list_my_appointments,
    request_human_handoff,
    now_in_salon_tz,
]
