from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.datetime_utils import (
    ensure_aware_in_timezone,
    is_future_in_reference_tz,
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
