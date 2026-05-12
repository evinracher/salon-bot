from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AppointmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class AppointmentCreate(BaseModel):
    customer_id: int = Field(gt=0)
    employee_id: int = Field(gt=0)
    service_id: int = Field(gt=0)
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus = AppointmentStatus.SCHEDULED

    @model_validator(mode="after")
    def validate_time_range(self) -> "AppointmentCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AppointmentUpdate(BaseModel):
    customer_id: int | None = Field(default=None, gt=0)
    employee_id: int | None = Field(default=None, gt=0)
    service_id: int | None = Field(default=None, gt=0)
    start_time: datetime | None = None
    end_time: datetime | None = None
    status: AppointmentStatus | None = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "AppointmentUpdate":
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("end_time must be after start_time")
        return self


class AppointmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    employee_id: int
    service_id: int
    start_time: datetime
    end_time: datetime
    status: AppointmentStatus
