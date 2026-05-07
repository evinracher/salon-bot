from datetime import datetime
from zoneinfo import ZoneInfo


def is_future_in_reference_tz(value: datetime) -> bool:
    return value > datetime.now(value.tzinfo)


def is_slot_boundary_in_timezone(
    *,
    value: datetime,
    interval_minutes: int,
    timezone_name: str,
) -> bool:
    local_value = value.astimezone(ZoneInfo(timezone_name))
    return (
        local_value.minute % interval_minutes == 0
        and local_value.second == 0
        and local_value.microsecond == 0
    )


def is_slot_duration_aligned(
    *,
    start: datetime,
    end: datetime,
    interval_minutes: int,
) -> bool:
    duration_seconds = (end - start).total_seconds()
    return duration_seconds > 0 and duration_seconds % (interval_minutes * 60) == 0


def normalize_to_second_in_timezone(value: datetime, timezone_name: str) -> datetime:
    return value.astimezone(ZoneInfo(timezone_name)).replace(microsecond=0)
