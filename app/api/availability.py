from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models.employee import Employee
from app.models.employee_service import EmployeeService
from app.schemas.availability import AvailabilityResponse
from app.services.salon_availability import (
    compute_availability_slots,
    resolve_service_duration_minutes,
)

router = APIRouter(prefix="/availability", tags=["availability"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_model=AvailabilityResponse)
async def get_availability(
    session: SessionDep,
    service_id: int = Query(gt=0),
    date_value: date = Query(alias="date"),
    employee_id: int | None = Query(default=None, gt=0),
    duration_minutes: int | None = Query(default=None, gt=0),
) -> AvailabilityResponse:
    service, selected_duration_minutes = await resolve_service_duration_minutes(
        session,
        service_id=service_id,
        duration_minutes=duration_minutes,
    )
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    if (
        selected_duration_minutes <= 0
        or selected_duration_minutes % settings.slot_interval_minutes != 0
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Service duration must be aligned to slot interval",
        )

    if employee_id is not None:
        employee = await session.get(Employee, employee_id)
        if employee is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
        relation = await session.scalar(
            select(EmployeeService.id).where(
                EmployeeService.employee_id == employee_id,
                EmployeeService.service_id == service_id,
            )
        )
        if relation is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Employee does not perform this service",
            )

    slots = await compute_availability_slots(
        session,
        service_id=service_id,
        date_value=date_value,
        employee_id=employee_id,
        selected_duration_minutes=selected_duration_minutes,
    )

    return AvailabilityResponse(
        service_id=service_id,
        employee_id=employee_id,
        date=date_value,
        timezone=settings.timezone,
        slot_interval_minutes=settings.slot_interval_minutes,
        service_duration_minutes=selected_duration_minutes,
        slots=slots,
    )
