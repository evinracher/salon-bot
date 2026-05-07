from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class EmployeeService(Base):
    __tablename__ = "employee_services"
    __table_args__ = (
        UniqueConstraint("employee_id", "service_id", name="uq_employee_services_pair"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
