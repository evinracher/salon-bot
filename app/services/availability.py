from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


def build_business_window(
    *,
    target_date: date,
    timezone_name: str,
    open_time: time,
    close_time: time,
    business_days: set[int] | frozenset[int],
) -> tuple[datetime, datetime] | None:
    if target_date.weekday() not in business_days:
        return None

    zone = ZoneInfo(timezone_name)
    open_dt = datetime.combine(target_date, open_time, tzinfo=zone)
    close_dt = datetime.combine(target_date, close_time, tzinfo=zone)
    return open_dt, close_dt


def generate_candidate_slots(
    *,
    open_dt: datetime,
    close_dt: datetime,
    slot_interval_minutes: int,
    service_duration_minutes: int,
) -> list[tuple[datetime, datetime]]:
    duration = timedelta(minutes=service_duration_minutes)
    step = timedelta(minutes=slot_interval_minutes)

    slots: list[tuple[datetime, datetime]] = []
    cursor = open_dt
    while cursor + duration <= close_dt:
        slots.append((cursor, cursor + duration))
        cursor += step
    return slots


def has_overlap(
    *,
    start: datetime,
    end: datetime,
    appointments: list[tuple[datetime, datetime]],
) -> bool:
    return any(
        not (end <= appt_start or start >= appt_end) for appt_start, appt_end in appointments
    )
