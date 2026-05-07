from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient


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


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _next_aligned_utc(minutes_ahead: int = 30) -> datetime:
    base = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    remainder = base.minute % 30
    aligned = base if remainder == 0 else base + timedelta(minutes=30 - remainder)
    return aligned + timedelta(minutes=minutes_ahead)


@pytest.mark.asyncio
async def test_appointment_create_and_get(client: AsyncClient) -> None:
    employee = await _create_employee(client, "11")
    service = await _create_service(client, "11")
    start = _next_aligned_utc()
    end = start + timedelta(minutes=30)

    create_resp = await client.post(
        "/appointments",
        json={
            "employee_id": employee["id"],
            "service_id": service["id"],
            "client_name": "John",
            "client_phone": "+1-222-0000",
            "start_time": _iso(start),
            "end_time": _iso(end),
            "status": "scheduled",
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()

    get_resp = await client.get(f"/appointments/{created['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["client_name"] == "John"


@pytest.mark.asyncio
async def test_appointment_fk_missing_returns_404(client: AsyncClient) -> None:
    start = _next_aligned_utc()
    end = start + timedelta(minutes=30)

    resp = await client.post(
        "/appointments",
        json={
            "employee_id": 99999999,
            "service_id": 99999999,
            "client_name": "X",
            "client_phone": "+1-222-0001",
            "start_time": _iso(start),
            "end_time": _iso(end),
            "status": "scheduled",
        },
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_appointment_invalid_time_returns_422(client: AsyncClient) -> None:
    employee = await _create_employee(client, "12")
    service = await _create_service(client, "12")
    start = datetime.now(timezone.utc).replace(microsecond=0)
    end = start

    resp = await client.post(
        "/appointments",
        json={
            "employee_id": employee["id"],
            "service_id": service["id"],
            "client_name": "X",
            "client_phone": "+1-222-0002",
            "start_time": _iso(start),
            "end_time": _iso(end),
            "status": "scheduled",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_appointment_start_time_must_be_future(client: AsyncClient) -> None:
    employee = await _create_employee(client, "12b")
    service = await _create_service(client, "12b")
    start = _next_aligned_utc(minutes_ahead=0) - timedelta(minutes=30)
    end = start + timedelta(minutes=30)

    resp = await client.post(
        "/appointments",
        json={
            "employee_id": employee["id"],
            "service_id": service["id"],
            "client_name": "Past",
            "client_phone": "+1-222-0010",
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
    employee = await _create_employee(client, "12c")
    service = await _create_service(client, "12c")
    start = _next_aligned_utc() + timedelta(minutes=7)
    end = start + timedelta(minutes=30)

    resp = await client.post(
        "/appointments",
        json={
            "employee_id": employee["id"],
            "service_id": service["id"],
            "client_name": "Unaligned",
            "client_phone": "+1-222-0012",
            "start_time": _iso(start),
            "end_time": _iso(end),
            "status": "scheduled",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_appointment_overlap_returns_409(client: AsyncClient) -> None:
    employee = await _create_employee(client, "13")
    service = await _create_service(client, "13")
    start = _next_aligned_utc()
    end = start + timedelta(minutes=30)
    overlap_start = start
    overlap_end = end

    first_resp = await client.post(
        "/appointments",
        json={
            "employee_id": employee["id"],
            "service_id": service["id"],
            "client_name": "First",
            "client_phone": "+1-222-0003",
            "start_time": _iso(start),
            "end_time": _iso(end),
            "status": "scheduled",
        },
    )
    assert first_resp.status_code == 201

    overlap_resp = await client.post(
        "/appointments",
        json={
            "employee_id": employee["id"],
            "service_id": service["id"],
            "client_name": "Second",
            "client_phone": "+1-222-0004",
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
    employee = await _create_employee(client, "14")
    service = await _create_service(client, "14")
    start = _next_aligned_utc()
    end = start + timedelta(minutes=30)

    cancelled_resp = await client.post(
        "/appointments",
        json={
            "employee_id": employee["id"],
            "service_id": service["id"],
            "client_name": "Cancelled",
            "client_phone": "+1-222-0005",
            "start_time": _iso(start),
            "end_time": _iso(end),
            "status": "cancelled",
        },
    )
    assert cancelled_resp.status_code == 201

    overlapping_resp = await client.post(
        "/appointments",
        json={
            "employee_id": employee["id"],
            "service_id": service["id"],
            "client_name": "Allowed",
            "client_phone": "+1-222-0006",
            "start_time": _iso(start),
            "end_time": _iso(end),
            "status": "scheduled",
        },
    )
    assert overlapping_resp.status_code == 201


@pytest.mark.asyncio
async def test_appointment_patch_overlap_returns_409(client: AsyncClient) -> None:
    employee = await _create_employee(client, "15")
    service = await _create_service(client, "15")
    start = _next_aligned_utc()
    end = start + timedelta(minutes=30)

    first = (
        await client.post(
            "/appointments",
            json={
                "employee_id": employee["id"],
                "service_id": service["id"],
                "client_name": "First",
                "client_phone": "+1-222-0007",
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
                "employee_id": employee["id"],
                "service_id": service["id"],
                "client_name": "Second",
                "client_phone": "+1-222-0008",
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
    employee = await _create_employee(client, "15b")
    service = await _create_service(client, "15b")
    start = _next_aligned_utc()
    end = start + timedelta(minutes=30)

    created = (
        await client.post(
            "/appointments",
            json={
                "employee_id": employee["id"],
                "service_id": service["id"],
                "client_name": "Future",
                "client_phone": "+1-222-0011",
                "start_time": _iso(start),
                "end_time": _iso(end),
                "status": "scheduled",
            },
        )
    ).json()

    past_start = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(
        minutes=15
    )
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
    employee = await _create_employee(client, "15c")
    service = await _create_service(client, "15c")
    start = _next_aligned_utc()
    end = start + timedelta(minutes=30)

    created = (
        await client.post(
            "/appointments",
            json={
                "employee_id": employee["id"],
                "service_id": service["id"],
                "client_name": "Aligned",
                "client_phone": "+1-222-0013",
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
    employee = await _create_employee(client, "16")
    service = await _create_service(client, "16")
    start = _next_aligned_utc()

    created = (
        await client.post(
            "/appointments",
            json={
                "employee_id": employee["id"],
                "service_id": service["id"],
                "client_name": "Filter",
                "client_phone": "+1-222-0009",
                "start_time": _iso(start),
                "end_time": _iso(start + timedelta(minutes=30)),
                "status": "confirmed",
            },
        )
    ).json()

    filtered = await client.get(
        f"/appointments?employee_id={employee['id']}&status=confirmed&from={_iso(start - timedelta(minutes=1))}&to={_iso(start + timedelta(minutes=1))}",
    )
    assert filtered.status_code == 200
    assert any(item["id"] == created["id"] for item in filtered.json())

    delete_resp = await client.delete(f"/appointments/{created['id']}")
    assert delete_resp.status_code == 204
    assert (await client.get(f"/appointments/{created['id']}")).status_code == 404


@pytest.mark.asyncio
async def test_appointment_allows_adjacent_time_ranges(client: AsyncClient) -> None:
    employee = await _create_employee(client, "17")
    service = await _create_service(client, "17")
    start = _next_aligned_utc()
    middle = start + timedelta(minutes=30)
    end = middle + timedelta(minutes=30)

    first = await client.post(
        "/appointments",
        json={
            "employee_id": employee["id"],
            "service_id": service["id"],
            "client_name": "First",
            "client_phone": "+1-333-0001",
            "start_time": _iso(start),
            "end_time": _iso(middle),
            "status": "scheduled",
        },
    )
    assert first.status_code == 201

    second = await client.post(
        "/appointments",
        json={
            "employee_id": employee["id"],
            "service_id": service["id"],
            "client_name": "Second",
            "client_phone": "+1-333-0002",
            "start_time": _iso(middle),
            "end_time": _iso(end),
            "status": "scheduled",
        },
    )
    assert second.status_code == 201
