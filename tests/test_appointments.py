from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from app.config import settings


async def _create_employee(client: AsyncClient, suffix: str) -> dict:
    return (
        await client.post(
            "/employees",
            json={"name": f"Emp{suffix}", "phone": f"+1-555-2{suffix}00"},
        )
    ).json()


async def _create_service(client: AsyncClient, suffix: str) -> dict:
    return (
        await client.post(
            "/services",
            json={"name": f"Svc{suffix}", "duration_minutes": 30, "price": "35.00"},
        )
    ).json()


async def _create_customer(client: AsyncClient, suffix: str) -> dict:
    return (
        await client.post(
            "/customers",
            json={"name": f"Cust{suffix}", "phone": f"+1-777-2{suffix}00"},
        )
    ).json()


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _next_aligned_utc(minutes_ahead: int = 30) -> datetime:
    base = datetime.now(UTC).replace(second=0, microsecond=0)
    remainder = base.minute % 30
    aligned = base if remainder == 0 else base + timedelta(minutes=30 - remainder)
    return aligned + timedelta(minutes=minutes_ahead)


@pytest.mark.asyncio
async def test_appointment_create_and_get(client: AsyncClient) -> None:
    customer = await _create_customer(client, "11")
    employee = await _create_employee(client, "11")
    service = await _create_service(client, "11")
    start = _next_aligned_utc()
    end = start + timedelta(minutes=30)

    create_resp = await client.post(
        "/appointments",
        json={
            "customer_id": customer["id"],
            "employee_id": employee["id"],
            "service_id": service["id"],
            "start_time": _iso(start),
            "end_time": _iso(end),
            "status": "scheduled",
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()

    get_resp = await client.get(f"/appointments/{created['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["customer_id"] == customer["id"]


@pytest.mark.asyncio
async def test_appointment_fk_missing_returns_404(client: AsyncClient) -> None:
    start = _next_aligned_utc()
    end = start + timedelta(minutes=30)

    resp = await client.post(
        "/appointments",
        json={
            "customer_id": 99999999,
            "employee_id": 99999999,
            "service_id": 99999999,
            "start_time": _iso(start),
            "end_time": _iso(end),
            "status": "scheduled",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_appointment_invalid_time_returns_422(client: AsyncClient) -> None:
    customer = await _create_customer(client, "12")
    employee = await _create_employee(client, "12")
    service = await _create_service(client, "12")
    start = datetime.now(UTC).replace(microsecond=0)
    end = start

    resp = await client.post(
        "/appointments",
        json={
            "customer_id": customer["id"],
            "employee_id": employee["id"],
            "service_id": service["id"],
            "start_time": _iso(start),
            "end_time": _iso(end),
            "status": "scheduled",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_appointment_start_time_must_be_future(client: AsyncClient) -> None:
    customer = await _create_customer(client, "12b")
    employee = await _create_employee(client, "12b")
    service = await _create_service(client, "12b")
    start = _next_aligned_utc(minutes_ahead=0) - timedelta(minutes=30)
    end = start + timedelta(minutes=30)

    resp = await client.post(
        "/appointments",
        json={
            "customer_id": customer["id"],
            "employee_id": employee["id"],
            "service_id": service["id"],
            "start_time": _iso(start),
            "end_time": _iso(end),
            "status": "scheduled",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_appointment_requires_slot_aligned_times_on_create(
    client: AsyncClient,
) -> None:
    customer = await _create_customer(client, "12c")
    employee = await _create_employee(client, "12c")
    service = await _create_service(client, "12c")
    start = _next_aligned_utc() + timedelta(minutes=7)
    end = start + timedelta(minutes=30)

    resp = await client.post(
        "/appointments",
        json={
            "customer_id": customer["id"],
            "employee_id": employee["id"],
            "service_id": service["id"],
            "start_time": _iso(start),
            "end_time": _iso(end),
            "status": "scheduled",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_appointment_overlap_returns_409(client: AsyncClient) -> None:
    customer = await _create_customer(client, "13")
    employee = await _create_employee(client, "13")
    service = await _create_service(client, "13")
    start = _next_aligned_utc()
    end = start + timedelta(minutes=30)
    overlap_start = start
    overlap_end = end

    first_resp = await client.post(
        "/appointments",
        json={
            "customer_id": customer["id"],
            "employee_id": employee["id"],
            "service_id": service["id"],
            "start_time": _iso(start),
            "end_time": _iso(end),
            "status": "scheduled",
        },
    )
    assert first_resp.status_code == 201

    overlap_resp = await client.post(
        "/appointments",
        json={
            "customer_id": customer["id"],
            "employee_id": employee["id"],
            "service_id": service["id"],
            "start_time": _iso(overlap_start),
            "end_time": _iso(overlap_end),
            "status": "scheduled",
        },
    )
    assert overlap_resp.status_code == 409


@pytest.mark.asyncio
async def test_appointment_overlap_allowed_if_existing_cancelled(
    client: AsyncClient,
) -> None:
    customer = await _create_customer(client, "14")
    employee = await _create_employee(client, "14")
    service = await _create_service(client, "14")
    start = _next_aligned_utc()
    end = start + timedelta(minutes=30)

    cancelled_resp = await client.post(
        "/appointments",
        json={
            "customer_id": customer["id"],
            "employee_id": employee["id"],
            "service_id": service["id"],
            "start_time": _iso(start),
            "end_time": _iso(end),
            "status": "cancelled",
        },
    )
    assert cancelled_resp.status_code == 201

    overlapping_resp = await client.post(
        "/appointments",
        json={
            "customer_id": customer["id"],
            "employee_id": employee["id"],
            "service_id": service["id"],
            "start_time": _iso(start),
            "end_time": _iso(end),
            "status": "scheduled",
        },
    )
    assert overlapping_resp.status_code == 201


@pytest.mark.asyncio
async def test_appointment_patch_overlap_returns_409(client: AsyncClient) -> None:
    customer = await _create_customer(client, "15")
    employee = await _create_employee(client, "15")
    service = await _create_service(client, "15")
    start = _next_aligned_utc()
    end = start + timedelta(minutes=30)

    first = (
        await client.post(
            "/appointments",
            json={
                "customer_id": customer["id"],
                "employee_id": employee["id"],
                "service_id": service["id"],
                "start_time": _iso(start),
                "end_time": _iso(end),
                "status": "scheduled",
            },
        )
    ).json()
    second = (
        await client.post(
            "/appointments",
            json={
                "customer_id": customer["id"],
                "employee_id": employee["id"],
                "service_id": service["id"],
                "start_time": _iso(end + timedelta(minutes=30)),
                "end_time": _iso(end + timedelta(minutes=60)),
                "status": "scheduled",
            },
        )
    ).json()

    resp = await client.patch(
        f"/appointments/{second['id']}",
        json={
            "start_time": _iso(start),
            "end_time": _iso(end),
        },
    )
    assert resp.status_code == 409
    assert first["id"] != second["id"]


@pytest.mark.asyncio
async def test_appointment_patch_rejects_past_start_time(client: AsyncClient) -> None:
    customer = await _create_customer(client, "15b")
    employee = await _create_employee(client, "15b")
    service = await _create_service(client, "15b")
    start = _next_aligned_utc()
    end = start + timedelta(minutes=30)

    created = (
        await client.post(
            "/appointments",
            json={
                "customer_id": customer["id"],
                "employee_id": employee["id"],
                "service_id": service["id"],
                "start_time": _iso(start),
                "end_time": _iso(end),
                "status": "scheduled",
            },
        )
    ).json()

    past_start = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=15)
    patch_resp = await client.patch(
        f"/appointments/{created['id']}",
        json={
            "start_time": _iso(past_start),
            "end_time": _iso(past_start + timedelta(minutes=30)),
        },
    )
    assert patch_resp.status_code == 422


@pytest.mark.asyncio
async def test_appointment_patch_rejects_unaligned_times(client: AsyncClient) -> None:
    customer = await _create_customer(client, "15c")
    employee = await _create_employee(client, "15c")
    service = await _create_service(client, "15c")
    start = _next_aligned_utc()
    end = start + timedelta(minutes=30)

    created = (
        await client.post(
            "/appointments",
            json={
                "customer_id": customer["id"],
                "employee_id": employee["id"],
                "service_id": service["id"],
                "start_time": _iso(start),
                "end_time": _iso(end),
                "status": "scheduled",
            },
        )
    ).json()

    patch_resp = await client.patch(
        f"/appointments/{created['id']}",
        json={
            "start_time": _iso(start + timedelta(minutes=5)),
            "end_time": _iso(end + timedelta(minutes=5)),
        },
    )
    assert patch_resp.status_code == 422


@pytest.mark.asyncio
async def test_appointment_list_filters_and_delete(client: AsyncClient) -> None:
    customer = await _create_customer(client, "16")
    employee = await _create_employee(client, "16")
    service = await _create_service(client, "16")
    start = _next_aligned_utc()

    created = (
        await client.post(
            "/appointments",
            json={
                "customer_id": customer["id"],
                "employee_id": employee["id"],
                "service_id": service["id"],
                "start_time": _iso(start),
                "end_time": _iso(start + timedelta(minutes=30)),
                "status": "confirmed",
            },
        )
    ).json()

    filtered = await client.get(
        "/appointments",
        params={
            "employee_id": employee["id"],
            "status": "confirmed",
            "from": _iso(start - timedelta(minutes=1)),
            "to": _iso(start + timedelta(minutes=1)),
        },
    )
    assert filtered.status_code == 200
    assert any(item["id"] == created["id"] for item in filtered.json())

    delete_resp = await client.delete(f"/appointments/{created['id']}")
    assert delete_resp.status_code == 204
    assert (await client.get(f"/appointments/{created['id']}")).status_code == 404


@pytest.mark.asyncio
async def test_appointment_list_naive_from_to_matches_aware_bounds(
    client: AsyncClient,
) -> None:
    """Naive ISO bounds are interpreted as salon wall clock (settings.timezone)."""
    customer = await _create_customer(client, "naivef")
    employee = await _create_employee(client, "naivef")
    service = await _create_service(client, "naivef")
    start = _next_aligned_utc()

    created = (
        await client.post(
            "/appointments",
            json={
                "customer_id": customer["id"],
                "employee_id": employee["id"],
                "service_id": service["id"],
                "start_time": _iso(start),
                "end_time": _iso(start + timedelta(minutes=30)),
                "status": "confirmed",
            },
        )
    ).json()

    tz = ZoneInfo(settings.timezone)
    local_start = start.astimezone(tz)
    from_naive = (local_start - timedelta(minutes=1)).replace(tzinfo=None)
    to_naive = (local_start + timedelta(minutes=1)).replace(tzinfo=None)

    naive_resp = await client.get(
        "/appointments",
        params={
            "employee_id": employee["id"],
            "status": "confirmed",
            "from": from_naive.isoformat(),
            "to": to_naive.isoformat(),
        },
    )
    aware_resp = await client.get(
        "/appointments",
        params={
            "employee_id": employee["id"],
            "status": "confirmed",
            "from": _iso(start - timedelta(minutes=1)),
            "to": _iso(start + timedelta(minutes=1)),
        },
    )
    assert naive_resp.status_code == 200
    assert aware_resp.status_code == 200
    naive_ids = {row["id"] for row in naive_resp.json()}
    aware_ids = {row["id"] for row in aware_resp.json()}
    assert naive_ids == aware_ids
    assert created["id"] in naive_ids


@pytest.mark.asyncio
async def test_appointment_allows_adjacent_time_ranges(client: AsyncClient) -> None:
    customer = await _create_customer(client, "17")
    employee = await _create_employee(client, "17")
    service = await _create_service(client, "17")
    start = _next_aligned_utc()
    middle = start + timedelta(minutes=30)
    end = middle + timedelta(minutes=30)

    first = await client.post(
        "/appointments",
        json={
            "customer_id": customer["id"],
            "employee_id": employee["id"],
            "service_id": service["id"],
            "start_time": _iso(start),
            "end_time": _iso(middle),
            "status": "scheduled",
        },
    )
    assert first.status_code == 201

    second = await client.post(
        "/appointments",
        json={
            "customer_id": customer["id"],
            "employee_id": employee["id"],
            "service_id": service["id"],
            "start_time": _iso(middle),
            "end_time": _iso(end),
            "status": "scheduled",
        },
    )
    assert second.status_code == 201
