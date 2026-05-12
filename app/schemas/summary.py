from datetime import date, datetime

from pydantic import BaseModel, Field


class WeeklySummaryCounts(BaseModel):
    total: int = Field(description="Appointments in range excluding cancelled")
    completed: int
    pending: int = Field(description="Non-cancelled in range that are not completed")


class WeeklySummaryTopService(BaseModel):
    service_id: int
    name: str
    appointments: int


class WeeklySummaryEmployeeCount(BaseModel):
    employee_id: int
    name: str
    appointments: int


class WeeklySummaryUpcomingItem(BaseModel):
    id: int
    start_time: datetime
    service_name: str
    employee_name: str


class WeeklySummaryRead(BaseModel):
    week_start: date
    week_end: date
    timezone: str
    counts: WeeklySummaryCounts
    most_requested_service: WeeklySummaryTopService | None
    appointments_by_employee: list[WeeklySummaryEmployeeCount]
    upcoming_appointments: list[WeeklySummaryUpcomingItem]
    upcoming_date: date = Field(
        description="Calendar day used for the upcoming list (salon timezone)",
    )
