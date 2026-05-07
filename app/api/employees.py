from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.employee import Employee
from app.schemas.employee import EmployeeCreate, EmployeeRead, EmployeeUpdate

router = APIRouter(prefix="/employees", tags=["employees"])
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.post("", response_model=EmployeeRead, status_code=status.HTTP_201_CREATED)
async def create_employee(
    body: EmployeeCreate,
    session: SessionDep,
) -> Employee:
    employee = Employee(name=body.name, phone=body.phone)
    session.add(employee)
    await session.commit()
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


@router.patch("/{employee_id}", response_model=EmployeeRead)
async def update_employee(
    employee_id: int,
    body: EmployeeUpdate,
    session: SessionDep,
) -> Employee:
    employee = await session.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    payload = body.model_dump(exclude_unset=True)
    for key, value in payload.items():
        setattr(employee, key, value)

    await session.commit()
    await session.refresh(employee)
    return employee


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employee(
    employee_id: int,
    session: SessionDep,
) -> None:
    employee = await session.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    await session.delete(employee)
    await session.commit()
