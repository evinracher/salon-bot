from datetime import date, datetime

from pydantic import BaseModel


class AvailabilitySlot(BaseModel):
    start: datetime
    end: datetime
    employee_ids: list[int]


class AvailabilityResponse(BaseModel):
    service_id: int
    employee_id: int | None
    date: date
    timezone: str
    slot_interval_minutes: int
    service_duration_minutes: int
    slots: list[AvailabilitySlot]
