from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate, EmployeeRead

router = APIRouter(prefix="/employees", tags=["employees"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
async def create_employee(
    body: EmployeeCreate,
    session: SessionDep,
) -> Employee:
    employee = Employee(name=body.name, phone=body.phone)
    session.add(employee)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee with this phone already exists",
        ) from exc
    await session.refresh(employee)
    return employee


@router.get("", response_model=list[EmployeeRead])
async def list_employees(
    session: SessionDep,
) -> list[Employee]:
    result = await session.scalars(select(Employee).order_by(Employee.id))
    return list(result.all())


@router.get("/{employee_id}", response_model=EmployeeRead)
async def get_employee(
    employee_id: int,
    session: SessionDep,
) -> Employee:
    employee = await session.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return employee
