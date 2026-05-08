from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.schemas.availability import AvailabilityResponse
from app.services.availability_service import (
    AvailabilityServiceError,
    compute_availability,
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
    try:
        return await compute_availability(
            session,
            service_id=service_id,
            date_value=date_value,
            employee_id=employee_id,
            duration_minutes=duration_minutes,
        )
    except AvailabilityServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
