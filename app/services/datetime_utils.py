from datetime import datetime
from zoneinfo import ZoneInfo


def ensure_aware_in_timezone(value: datetime, timezone_name: str) -> datetime:
    """Attach or convert to ``timezone_name`` (naive values are wall-clock in that zone)."""
    tz = ZoneInfo(timezone_name)
    if value.tzinfo is None:
        return value.replace(tzinfo=tz)
    return value.astimezone(tz)


def is_future_in_reference_tz(value: datetime, *, reference_timezone_name: str) -> bool:
    """
    True if ``value`` is strictly after "now" in ``reference_timezone_name``.

    Naive datetimes are treated as local wall time in that zone (not the host OS zone).
    """
    aware = ensure_aware_in_timezone(value, reference_timezone_name)
    tz = ZoneInfo(reference_timezone_name)
    return aware > datetime.now(tz)


def is_slot_boundary_in_timezone(
    *,
    value: datetime,
    interval_minutes: int,
    timezone_name: str,
) -> bool:
    local_value = ensure_aware_in_timezone(value, timezone_name)
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
    aware = ensure_aware_in_timezone(value, timezone_name)
    return aware.astimezone(ZoneInfo(timezone_name)).replace(microsecond=0)
