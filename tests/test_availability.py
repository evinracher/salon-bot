import pytest
from httpx import AsyncClient


async def _create_employee(client: AsyncClient, suffix: str) -> dict:
    return (
        await client.post(
            "/employees",
            json={"name": f"Emp{suffix}", "phone": f"+1-444-{suffix}00"},
        )
    ).json()


async def _create_service(client: AsyncClient, suffix: str, duration: int) -> dict:
    return (
        await client.post(
            "/services",
            json={
                "name": f"Svc{suffix}",
                "duration_minutes": duration,
                "price": "45.00",
            },
        )
    ).json()


async def _create_customer(client: AsyncClient, suffix: str) -> dict:
    return (
        await client.post(
            "/customers",
            json={"name": f"Cust{suffix}", "phone": f"+1-666-{suffix}00"},
        )
    ).json()


async def _link_employee_service(client: AsyncClient, employee_id: int, service_id: int) -> None:
    response = await client.post(
        "/employee-services",
        json={"employee_id": employee_id, "service_id": service_id},
    )
    assert response.status_code == 201


def _slot_starts(payload: dict) -> list[str]:
    return [slot["start"] for slot in payload["slots"]]


def _slot_by_start(payload: dict, start: str) -> dict:
    for slot in payload["slots"]:
        if slot["start"] == start:
            return slot
    raise AssertionError(f"Slot {start} not found")


@pytest.mark.asyncio
async def test_availability_service_day_returns_expected_slot_counts(
    client: AsyncClient,
) -> None:
    employee = await _create_employee(client, "a1")
    service_30 = await _create_service(client, "a1", duration=30)
    service_90 = await _create_service(client, "a2", duration=90)
    await _link_employee_service(client, employee["id"], service_30["id"])
    await _link_employee_service(client, employee["id"], service_90["id"])

    resp_30 = await client.get(f"/availability?service_id={service_30['id']}&date=2026-05-11")
    assert resp_30.status_code == 200
    body_30 = resp_30.json()
    assert len(body_30["slots"]) == 18
    assert body_30["slots"][0]["employee_ids"] == [employee["id"]]

    resp_90 = await client.get(f"/availability?service_id={service_90['id']}&date=2026-05-11")
    assert resp_90.status_code == 200
    body_90 = resp_90.json()
    assert len(body_90["slots"]) == 16
    assert body_90["slots"][-1]["start"].startswith("2026-05-11T17:30:00")


@pytest.mark.asyncio
async def test_availability_last_start_for_one_hour_service(
    client: AsyncClient,
) -> None:
    employee = await _create_employee(client, "a3")
    service = await _create_service(client, "a3", duration=60)
    await _link_employee_service(client, employee["id"], service["id"])

    resp = await client.get(f"/availability?service_id={service['id']}&date=2026-05-11")
    assert resp.status_code == 200
    assert resp.json()["slots"][-1]["start"].startswith("2026-05-11T18:00:00")


@pytest.mark.asyncio
async def test_availability_closed_day_returns_empty(client: AsyncClient) -> None:
    employee = await _create_employee(client, "a4")
    service = await _create_service(client, "a4", duration=30)
    await _link_employee_service(client, employee["id"], service["id"])

    resp = await client.get(f"/availability?service_id={service['id']}&date=2026-05-10")
    assert resp.status_code == 200
    assert resp.json()["slots"] == []


@pytest.mark.asyncio
async def test_availability_employee_filter_and_union_behavior(
    client: AsyncClient,
) -> None:
    employee_1 = await _create_employee(client, "a5")
    employee_2 = await _create_employee(client, "a6")
    customer = await _create_customer(client, "a5")
    service = await _create_service(client, "a5", duration=30)
    await _link_employee_service(client, employee_1["id"], service["id"])
    await _link_employee_service(client, employee_2["id"], service["id"])

    appointment = await client.post(
        "/appointments",
        json={
            "customer_id": customer["id"],
            "employee_id": employee_1["id"],
            "service_id": service["id"],
            "start_time": "2030-06-03T10:00:00-05:00",
            "end_time": "2030-06-03T10:30:00-05:00",
            "status": "scheduled",
        },
    )
    assert appointment.status_code == 201

    employee_resp = await client.get(
        f"/availability?service_id={service['id']}&employee_id={employee_1['id']}&date=2030-06-03"
    )
    assert employee_resp.status_code == 200
    employee_slots = _slot_starts(employee_resp.json())
    assert "2030-06-03T10:00:00-05:00" not in employee_slots

    union_resp = await client.get(f"/availability?service_id={service['id']}&date=2030-06-03")
    assert union_resp.status_code == 200
    union_body = union_resp.json()
    union_slots = _slot_starts(union_body)
    assert "2030-06-03T10:00:00-05:00" in union_slots
    assert _slot_by_start(union_body, "2030-06-03T10:00:00-05:00")["employee_ids"] == [
        employee_2["id"]
    ]


@pytest.mark.asyncio
async def test_availability_employee_not_linked_returns_400(
    client: AsyncClient,
) -> None:
    employee = await _create_employee(client, "a7")
    service = await _create_service(client, "a7", duration=30)

    resp = await client.get(
        f"/availability?service_id={service['id']}&employee_id={employee['id']}&date=2026-05-11"
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_availability_cancelled_appointment_does_not_block(
    client: AsyncClient,
) -> None:
    employee = await _create_employee(client, "a8")
    customer = await _create_customer(client, "a8")
    service = await _create_service(client, "a8", duration=30)
    await _link_employee_service(client, employee["id"], service["id"])

    cancelled = await client.post(
        "/appointments",
        json={
            "customer_id": customer["id"],
            "employee_id": employee["id"],
            "service_id": service["id"],
            "start_time": "2030-06-03T10:00:00-05:00",
            "end_time": "2030-06-03T10:30:00-05:00",
            "status": "cancelled",
        },
    )
    assert cancelled.status_code == 201

    resp = await client.get(
        f"/availability?service_id={service['id']}&employee_id={employee['id']}&date=2030-06-03"
    )
    assert resp.status_code == 200
    assert "2030-06-03T10:00:00-05:00" in _slot_starts(resp.json())


@pytest.mark.asyncio
async def test_availability_unknown_ids_return_404(client: AsyncClient) -> None:
    missing_service = await client.get("/availability?service_id=999999&date=2026-05-11")
    assert missing_service.status_code == 404

    service = await _create_service(client, "a9", duration=30)
    missing_employee = await client.get(
        f"/availability?service_id={service['id']}&employee_id=999999&date=2026-05-11"
    )
    assert missing_employee.status_code == 404


@pytest.mark.asyncio
async def test_availability_allows_duration_override(client: AsyncClient) -> None:
    employee = await _create_employee(client, "b1")
    service = await _create_service(client, "b1", duration=30)
    await _link_employee_service(client, employee["id"], service["id"])

    resp = await client.get(
        f"/availability?service_id={service['id']}&date=2026-05-11&duration_minutes=90"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["service_duration_minutes"] == 90
    assert len(body["slots"]) == 16

    bad = await client.get(
        f"/availability?service_id={service['id']}&date=2026-05-11&duration_minutes=25"
    )
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_availability_restarts_exactly_at_appointment_end(
    client: AsyncClient,
) -> None:
    employee = await _create_employee(client, "b2")
    customer = await _create_customer(client, "b2")
    service = await _create_service(client, "b2", duration=30)
    await _link_employee_service(client, employee["id"], service["id"])

    existing = await client.post(
        "/appointments",
        json={
            "customer_id": customer["id"],
            "employee_id": employee["id"],
            "service_id": service["id"],
            "start_time": "2030-06-03T11:00:00-05:00",
            "end_time": "2030-06-03T11:30:00-05:00",
            "status": "scheduled",
        },
    )
    assert existing.status_code == 201

    resp = await client.get(
        f"/availability?service_id={service['id']}&employee_id={employee['id']}&date=2030-06-03"
    )
    assert resp.status_code == 200
    starts = _slot_starts(resp.json())
    assert "2030-06-03T11:00:00-05:00" not in starts
    assert "2030-06-03T11:30:00-05:00" in starts


@pytest.mark.asyncio
async def test_availability_rejects_microsecond_appointment_payload(
    client: AsyncClient,
) -> None:
    employee = await _create_employee(client, "b3")
    customer = await _create_customer(client, "b3")
    service = await _create_service(client, "b3", duration=60)
    await _link_employee_service(client, employee["id"], service["id"])

    appointment = await client.post(
        "/appointments",
        json={
            "customer_id": customer["id"],
            "employee_id": employee["id"],
            "service_id": service["id"],
            "start_time": "2026-05-07T15:00:00.075000Z",
            "end_time": "2026-05-07T16:30:00.075000Z",
            "status": "scheduled",
        },
    )
    assert appointment.status_code == 422
