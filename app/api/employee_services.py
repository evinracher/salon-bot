from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.employee import Employee
from app.models.employee_service import EmployeeService
from app.models.service import Service
from app.schemas.employee_service import EmployeeServiceCreate, EmployeeServiceRead

router = APIRouter(prefix="/employee-services", tags=["employee-services"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post(
    "", response_model=EmployeeServiceRead, status_code=status.HTTP_201_CREATED
)
async def create_employee_service(
    body: EmployeeServiceCreate,
    session: SessionDep,
) -> EmployeeService:
    employee = await session.get(Employee, body.employee_id)
    if employee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        )

    service = await session.get(Service, body.service_id)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service not found"
        )

    employee_service = EmployeeService(**body.model_dump())
    session.add(employee_service)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee already linked to this service",
        ) from exc
    await session.refresh(employee_service)
    return employee_service


@router.get("", response_model=list[EmployeeServiceRead])
async def list_employee_services(
    session: SessionDep,
    employee_id: int | None = Query(default=None, gt=0),
    service_id: int | None = Query(default=None, gt=0),
) -> list[EmployeeService]:
    stmt: Select[tuple[EmployeeService]] = select(EmployeeService)
    if employee_id is not None:
        stmt = stmt.where(EmployeeService.employee_id == employee_id)
    if service_id is not None:
        stmt = stmt.where(EmployeeService.service_id == service_id)
    stmt = stmt.order_by(EmployeeService.id)
    result = await session.scalars(stmt)
    return list(result.all())


@router.get("/{employee_service_id}", response_model=EmployeeServiceRead)
async def get_employee_service(
    employee_service_id: int,
    session: SessionDep,
) -> EmployeeService:
    employee_service = await session.get(EmployeeService, employee_service_id)
    if employee_service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return employee_service


@router.delete("/{employee_service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee_service(
    employee_service_id: int,
    session: SessionDep,
) -> None:
    employee_service = await session.get(EmployeeService, employee_service_id)
    if employee_service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await session.delete(employee_service)
    await session.commit()
