from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_customer(client: AsyncClient) -> None:
    resp = await client.post(
        "/customers",
        json={"name": "Ada", "phone": "+1-555-1100", "notes": "VIP"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Ada"
    assert data["phone"] == "+1-555-1100"
    assert data["notes"] == "VIP"
    assert data["id"] >= 1
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_customer_duplicate_phone_returns_409(client: AsyncClient) -> None:
    await client.post(
        "/customers",
        json={"name": "First", "phone": "+1-555-1200"},
    )
    resp = await client.post(
        "/customers",
        json={"name": "Second", "phone": "+1-555-1200"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Customer phone already exists"


@pytest.mark.asyncio
async def test_create_customer_validation_empty_name(client: AsyncClient) -> None:
    resp = await client.post(
        "/customers",
        json={"name": "", "phone": "+1-555-1300"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_customers_includes_created(client: AsyncClient) -> None:
    await client.post(
        "/customers",
        json={"name": "Listed", "phone": "+1-555-1400"},
    )
    resp = await client.get("/customers")
    assert resp.status_code == 200
    items = resp.json()
    assert any(c["phone"] == "+1-555-1400" and c["name"] == "Listed" for c in items)


@pytest.mark.asyncio
async def test_get_customer_by_id(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/customers",
            json={"name": "ById", "phone": "+1-555-1500"},
        )
    ).json()
    cid = created["id"]
    resp = await client.get(f"/customers/{cid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == cid
    assert body["name"] == "ById"
    assert body["phone"] == "+1-555-1500"


@pytest.mark.asyncio
async def test_get_customer_missing_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/customers/999999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_customer(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/customers",
            json={"name": "Before", "phone": "+1-555-1600"},
        )
    ).json()

    resp = await client.patch(
        f"/customers/{created['id']}",
        json={"name": "After", "notes": "note"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "After"
    assert resp.json()["phone"] == "+1-555-1600"
    assert resp.json()["notes"] == "note"


@pytest.mark.asyncio
async def test_update_customer_phone(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/customers",
            json={"name": "Mover", "phone": "+1-555-1700"},
        )
    ).json()

    resp = await client.patch(
        f"/customers/{created['id']}",
        json={"phone": "+1-555-1701"},
    )
    assert resp.status_code == 200
    assert resp.json()["phone"] == "+1-555-1701"


@pytest.mark.asyncio
async def test_update_customer_duplicate_phone_returns_409(client: AsyncClient) -> None:
    first = (
        await client.post(
            "/customers",
            json={"name": "A", "phone": "+1-555-1800"},
        )
    ).json()
    await client.post(
        "/customers",
        json={"name": "B", "phone": "+1-555-1801"},
    )

    resp = await client.patch(
        f"/customers/{first['id']}",
        json={"phone": "+1-555-1801"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_customer_missing_returns_404(client: AsyncClient) -> None:
    resp = await client.patch("/customers/999999999", json={"name": "Nope"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_customer(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/customers",
            json={"name": "Delete", "phone": "+1-555-1900"},
        )
    ).json()

    resp = await client.delete(f"/customers/{created['id']}")
    assert resp.status_code == 204

    get_resp = await client.get(f"/customers/{created['id']}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_customer_missing_returns_404(client: AsyncClient) -> None:
    resp = await client.delete("/customers/999999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_customer_with_appointment_returns_409(client: AsyncClient) -> None:
    emp = (
        await client.post(
            "/employees",
            json={"name": "E", "phone": "+1-555-2000"},
        )
    ).json()
    svc = (
        await client.post(
            "/services",
            json={"name": "S", "duration_minutes": 30, "price": "10.00"},
        )
    ).json()
    cust = (
        await client.post(
            "/customers",
            json={"name": "Booked", "phone": "+1-555-2001"},
        )
    ).json()
    base = datetime.now(UTC).replace(second=0, microsecond=0)
    remainder = base.minute % 30
    start = base if remainder == 0 else base + timedelta(minutes=30 - remainder)
    start = start + timedelta(minutes=30)
    end = start + timedelta(minutes=30)
    start_s = start.isoformat().replace("+00:00", "Z")
    end_s = end.isoformat().replace("+00:00", "Z")
    appt = await client.post(
        "/appointments",
        json={
            "customer_id": cust["id"],
            "employee_id": emp["id"],
            "service_id": svc["id"],
            "start_time": start_s,
            "end_time": end_s,
            "status": "scheduled",
        },
    )
    assert appt.status_code == 201, appt.text

    resp = await client.delete(f"/customers/{cust['id']}")
    assert resp.status_code == 409
