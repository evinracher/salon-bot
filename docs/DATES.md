# Dates and timezones

## Policy (single source of truth)

1. **Database:** all business timestamps use SQLAlchemy **`DateTime(timezone=True)`** (PostgreSQL `timestamptz`). Server defaults use `func.now()` where applicable.
2. **Salon zone:** business rules (opening hours, slot grid, "is this in the future?") use **`settings.timezone`** (IANA name, e.g. `America/Bogota`). The value is validated at settings load with **`ZoneInfo`**.
3. **Naive datetimes:** when a `datetime` has **`tzinfo is None`**, helpers treat it as **wall-clock time in `settings.timezone`**, not the host OS local zone. This is implemented in **`ensure_aware_in_timezone`** (`app/services/datetime_utils.py`).
4. **API responses:** Pydantic/FastAPI serialize aware datetimes as **ISO 8601 with offset**. Clients should send aware ISO strings or naive strings intentionally meaning salon local wall time.

## Helper functions (`app/services/datetime_utils.py`)

| Function | Behavior |
|----------|----------|
| `ensure_aware_in_timezone(dt, tz_name)` | Naive: `replace(tzinfo=ZoneInfo(tz_name))`. Aware: `astimezone(ZoneInfo(tz_name))`. |
| `is_future_in_reference_tz(dt, reference_timezone_name=...)` | Uses `ensure_aware_in_timezone` then compares to `datetime.now` in that zone. |
| `is_slot_boundary_in_timezone(...)` | Normalizes with `ensure_aware_in_timezone` first, then checks minute/second/microsecond against `interval_minutes` in the salon zone. |
| `normalize_to_second_in_timezone(dt, tz_name)` | Normalizes with `ensure_aware_in_timezone`, then strips sub-second precision in the salon zone. |
| `is_slot_duration_aligned(...)` | Pure timedelta math on the given start/end (callers should pass aligned-aware instants). |

**Important:** Always normalize user/API inputs with **`ensure_aware_in_timezone`** before slot-boundary checks or DB comparisons when naive ISO strings are possible (e.g. `GET /appointments?from=&to=`).

## Slot grid

- Config: **`slot_interval_minutes`**, **`business_open_time`**, **`business_close_time`**, **`business_days`** (`app/config.py`).
- Candidate slots: **`build_business_window`** + **`generate_candidate_slots`** (`app/services/availability.py`).
- Overlap checks: **`has_overlap`** + appointment rows normalized with **`normalize_to_second_in_timezone`** in **`compute_availability_slots`** (`app/services/salon_availability.py`).

## DST and zone changes

- **`ZoneInfo`** follows IANA rules. **`America/Bogota`** has no DST; if `TIMEZONE` is changed to a DST region, ambiguous/nonexistent local times around transitions are not specially tested in this repo yet (see [RECOMMENDATIONS.md](RECOMMENDATIONS.md)).

## Agent / tools

- **`runner.run_turn`** injects **`current_local_datetime`** into the system prompt as an ISO string in **`settings.timezone`**.
- Tools use **`date.fromisoformat`** (`YYYY-MM-DD`) and **`datetime.fromisoformat`** for booking starts, then **`ensure_aware_in_timezone`** before validation.

## Related files

- `app/api/appointments.py` — create/update/list filters
- `app/api/availability.py` — calendar `date` + slot `datetime`s
- `app/schemas/appointment.py`, `app/schemas/availability.py`
- `app/chat/agent/tools.py`, `app/chat/agent/prompts.py`
