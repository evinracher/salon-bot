from datetime import date, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models.appointment import Appointment
from app.models.customer import Customer
from app.models.employee import Employee
from app.models.service import Service
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentRead,
    AppointmentStatus,
    AppointmentUpdate,
)
from app.schemas.summary import (
    WeeklySummaryCounts,
    WeeklySummaryEmployeeCount,
    WeeklySummaryRead,
    WeeklySummaryTopService,
    WeeklySummaryUpcomingItem,
)
from app.services.datetime_utils import (
    ensure_aware_in_timezone,
    is_future_in_reference_tz,
    is_slot_boundary_in_timezone,
    is_slot_duration_aligned,
)

router = APIRouter(prefix="/appointments", tags=["appointments"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]

_MAX_SUMMARY_RANGE_DAYS = 120


def _monday_and_sunday_for_date(d: date) -> tuple[date, date]:
    monday = d - timedelta(days=d.weekday())
    return monday, monday + timedelta(days=6)


def _resolve_summary_week(
    week_start: date | None,
    week_end: date | None,
    timezone_name: str,
) -> tuple[date, date]:
    tz = ZoneInfo(timezone_name)
    today = datetime.now(tz).date()
    if week_start is None and week_end is None:
        return _monday_and_sunday_for_date(today)
    if week_start is not None and week_end is None:
        return week_start, week_start + timedelta(days=6)
    if week_start is None and week_end is not None:
        return week_end - timedelta(days=6), week_end
    assert week_start is not None
    assert week_end is not None
    return week_start, week_end


async def _ensure_refs_exist(
    session: AsyncSession,
    customer_id: int,
    employee_id: int,
    service_id: int,
) -> None:
    customer = await session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    employee = await session.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    service = await session.get(Service, service_id)
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")


async def _has_conflict(
    session: AsyncSession,
    employee_id: int,
    start_time: datetime,
    end_time: datetime,
    exclude_id: int | None = None,
) -> bool:
    stmt = select(Appointment.id).where(
        Appointment.employee_id == employee_id,
        Appointment.status != AppointmentStatus.CANCELLED.value,
        Appointment.start_time < end_time,
        Appointment.end_time > start_time,
    )
    if exclude_id is not None:
        stmt = stmt.where(Appointment.id != exclude_id)
    return (await session.scalar(stmt.limit(1))) is not None


def _validate_time_window(start_time: datetime, end_time: datetime) -> None:
    if end_time <= start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end_time must be after start_time",
        )


def _validate_future_start_time(start_time: datetime) -> None:
    if not is_future_in_reference_tz(start_time, reference_timezone_name=settings.timezone):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="start_time must be in the future",
        )


def _validate_slot_alignment(start_time: datetime, end_time: datetime) -> None:
    interval = settings.slot_interval_minutes

    aligned_start = is_slot_boundary_in_timezone(
        value=start_time,
        interval_minutes=interval,
        timezone_name=settings.timezone,
    )
    aligned_end = is_slot_boundary_in_timezone(
        value=end_time,
        interval_minutes=interval,
        timezone_name=settings.timezone,
    )
    aligned_duration = is_slot_duration_aligned(
        start=start_time,
        end=end_time,
        interval_minutes=interval,
    )

    if not (aligned_start and aligned_end and aligned_duration):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Appointment times must align to slot interval "
                f"({interval} minutes) in {settings.timezone}"
            ),
        )


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    body: AppointmentCreate,
    session: SessionDep,
) -> Appointment:
    body = body.model_copy(
        update={
            "start_time": ensure_aware_in_timezone(body.start_time, settings.timezone),
            "end_time": ensure_aware_in_timezone(body.end_time, settings.timezone),
        }
    )
    await _ensure_refs_exist(session, body.customer_id, body.employee_id, body.service_id)
    _validate_slot_alignment(body.start_time, body.end_time)
    _validate_future_start_time(body.start_time)

    if body.status != AppointmentStatus.CANCELLED:
        has_conflict = await _has_conflict(
            session,
            body.employee_id,
            body.start_time,
            body.end_time,
        )
        if has_conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Appointment overlaps existing booking for this employee",
            )

    payload = body.model_dump()
    payload["status"] = body.status.value
    appointment = Appointment(**payload)
    session.add(appointment)
    await session.commit()
    await session.refresh(appointment)
    return appointment


@router.get("", response_model=list[AppointmentRead])
async def list_appointments(
    session: SessionDep,
    employee_id: int | None = Query(default=None, gt=0),
    status_filter: AppointmentStatus | None = Query(default=None, alias="status"),
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
) -> list[Appointment]:
    stmt: Select[tuple[Appointment]] = select(Appointment)
    if employee_id is not None:
        stmt = stmt.where(Appointment.employee_id == employee_id)
    if status_filter is not None:
        stmt = stmt.where(Appointment.status == status_filter.value)
    if from_time is not None:
        from_bound = ensure_aware_in_timezone(from_time, settings.timezone)
        stmt = stmt.where(Appointment.start_time >= from_bound)
    if to_time is not None:
        to_bound = ensure_aware_in_timezone(to_time, settings.timezone)
        stmt = stmt.where(Appointment.start_time <= to_bound)

    result = await session.scalars(stmt.order_by(Appointment.start_time, Appointment.id))
    return list(result.all())


@router.get("/weekly-summary", response_model=WeeklySummaryRead)
async def weekly_appointments_summary(
    session: SessionDep,
    week_start: date | None = Query(default=None),
    week_end: date | None = Query(default=None),
    upcoming_on: date | None = Query(
        default=None,
        description="Day for upcoming list (salon timezone). Defaults to today.",
    ),
) -> WeeklySummaryRead:
    tz_name = settings.timezone
    tz = ZoneInfo(tz_name)
    resolved_start, resolved_end = _resolve_summary_week(week_start, week_end, tz_name)
    if resolved_end < resolved_start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="week_end must be on or after week_start",
        )
    if (resolved_end - resolved_start).days > _MAX_SUMMARY_RANGE_DAYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Date range must not exceed {_MAX_SUMMARY_RANGE_DAYS + 1} days",
        )

    range_start = ensure_aware_in_timezone(
        datetime.combine(resolved_start, time.min),
        tz_name,
    )
    range_end_exclusive = ensure_aware_in_timezone(
        datetime.combine(resolved_end + timedelta(days=1), time.min),
        tz_name,
    )

    active_in_range = and_(
        Appointment.start_time >= range_start,
        Appointment.start_time < range_end_exclusive,
        Appointment.status != AppointmentStatus.CANCELLED.value,
    )

    total = int(
        await session.scalar(
            select(func.count()).select_from(Appointment).where(active_in_range),
        )
        or 0,
    )
    completed = int(
        await session.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(
                active_in_range,
                Appointment.status == AppointmentStatus.COMPLETED.value,
            ),
        )
        or 0,
    )
    pending = total - completed

    top_row = (
        await session.execute(
            select(Service.id, Service.name, func.count(Appointment.id))
            .join(Appointment, Appointment.service_id == Service.id)
            .where(active_in_range)
            .group_by(Service.id, Service.name)
            .order_by(func.count(Appointment.id).desc(), Service.name.asc(), Service.id.asc())
            .limit(1),
        )
    ).one_or_none()

    most_requested: WeeklySummaryTopService | None
    if top_row is None:
        most_requested = None
    else:
        sid, sname, scount = top_row
        most_requested = WeeklySummaryTopService(
            service_id=sid,
            name=sname,
            appointments=int(scount),
        )

    by_employee_rows = (
        await session.execute(
            select(Employee.id, Employee.name, func.count(Appointment.id))
            .join(Appointment, Appointment.employee_id == Employee.id)
            .where(active_in_range)
            .group_by(Employee.id, Employee.name)
            .order_by(Employee.name.asc(), Employee.id.asc()),
        )
    ).all()

    upcoming_day = upcoming_on if upcoming_on is not None else datetime.now(tz).date()
    day_start = ensure_aware_in_timezone(datetime.combine(upcoming_day, time.min), tz_name)
    day_end_exclusive = day_start + timedelta(days=1)
    now_local = datetime.now(tz)
    lower_bound = day_start if upcoming_day != now_local.date() else max(day_start, now_local)

    upcoming_rows = (
        await session.execute(
            select(Appointment.id, Appointment.start_time, Service.name, Employee.name)
            .join(Service, Service.id == Appointment.service_id)
            .join(Employee, Employee.id == Appointment.employee_id)
            .where(
                Appointment.start_time >= lower_bound,
                Appointment.start_time < day_end_exclusive,
                Appointment.status.in_(
                    (
                        AppointmentStatus.SCHEDULED.value,
                        AppointmentStatus.CONFIRMED.value,
                    ),
                ),
            )
            .order_by(Appointment.start_time.asc(), Appointment.id.asc()),
        )
    ).all()

    return WeeklySummaryRead(
        week_start=resolved_start,
        week_end=resolved_end,
        timezone=tz_name,
        counts=WeeklySummaryCounts(total=total, completed=completed, pending=pending),
        most_requested_service=most_requested,
        appointments_by_employee=[
            WeeklySummaryEmployeeCount(
                employee_id=row[0],
                name=row[1],
                appointments=int(row[2]),
            )
            for row in by_employee_rows
        ],
        upcoming_appointments=[
            WeeklySummaryUpcomingItem(
                id=row[0],
                start_time=row[1],
                service_name=row[2],
                employee_name=row[3],
            )
            for row in upcoming_rows
        ],
        upcoming_date=upcoming_day,
    )


@router.get("/{appointment_id}", response_model=AppointmentRead)
async def get_appointment(appointment_id: int, session: SessionDep) -> Appointment:
    appointment = await session.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return appointment


@router.patch("/{appointment_id}", response_model=AppointmentRead)
async def update_appointment(
    appointment_id: int,
    body: AppointmentUpdate,
    session: SessionDep,
) -> Appointment:
    appointment = await session.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    payload = body.model_dump(exclude_unset=True)
    target_employee_id = payload.get("employee_id", appointment.employee_id)
    target_service_id = payload.get("service_id", appointment.service_id)
    target_customer_id = payload.get("customer_id", appointment.customer_id)
    target_start_time = ensure_aware_in_timezone(
        payload.get("start_time", appointment.start_time),
        settings.timezone,
    )
    target_end_time = ensure_aware_in_timezone(
        payload.get("end_time", appointment.end_time),
        settings.timezone,
    )
    target_status = payload.get("status", AppointmentStatus(appointment.status))

    _validate_time_window(target_start_time, target_end_time)
    _validate_slot_alignment(target_start_time, target_end_time)
    _validate_future_start_time(target_start_time)
    await _ensure_refs_exist(
        session,
        target_customer_id,
        target_employee_id,
        target_service_id,
    )

    if target_status != AppointmentStatus.CANCELLED:
        has_conflict = await _has_conflict(
            session,
            target_employee_id,
            target_start_time,
            target_end_time,
            exclude_id=appointment_id,
        )
        if has_conflict:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Appointment overlaps existing booking for this employee",
            )

    for key, value in payload.items():
        if key == "start_time":
            value = target_start_time
        elif key == "end_time":
            value = target_end_time
        setattr(
            appointment,
            key,
            value.value if isinstance(value, AppointmentStatus) else value,
        )

    await session.commit()
    await session.refresh(appointment)
    return appointment


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_appointment(appointment_id: int, session: SessionDep) -> None:
    appointment = await session.get(Appointment, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await session.delete(appointment)
    await session.commit()
