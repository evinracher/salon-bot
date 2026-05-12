from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.datetime_utils import (
    ensure_aware_in_timezone,
    is_future_in_reference_tz,
    is_slot_boundary_in_timezone,
    normalize_to_second_in_timezone,
)


def test_ensure_aware_interprets_naive_as_wall_clock_in_zone() -> None:
    naive = datetime(2099, 6, 15, 14, 0, 0)
    aware = ensure_aware_in_timezone(naive, "America/Bogota")
    assert aware.tzinfo == ZoneInfo("America/Bogota")
    assert aware.hour == 14


def test_is_future_accepts_naive_in_reference_zone() -> None:
    assert is_future_in_reference_tz(
        datetime(2099, 1, 1, 12, 0, 0),
        reference_timezone_name="America/Bogota",
    )


def test_slot_boundary_naive_is_wall_clock_in_zone_not_host_local() -> None:
    """Naive 14:30 must mean 14:30 Bogota for boundary checks (not system local)."""
    naive = datetime(2099, 6, 15, 14, 30, 0, 0)
    assert is_slot_boundary_in_timezone(
        value=naive,
        interval_minutes=30,
        timezone_name="America/Bogota",
    )


def test_normalize_to_second_naive_wall_clock_in_zone() -> None:
    naive = datetime(2099, 6, 15, 14, 0, 30, 123456)
    out = normalize_to_second_in_timezone(naive, "America/Bogota")
    assert out.microsecond == 0
    assert out.second == 30
    assert out.minute == 0
    assert out.hour == 14
    assert out.tzinfo == ZoneInfo("America/Bogota")
