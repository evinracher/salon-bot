import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_employee(client: AsyncClient) -> None:
    resp = await client.post(
        "/employees",
        json={"name": "Ada", "phone": "+1-555-0100"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Ada"
    assert data["phone"] == "+1-555-0100"
    assert data["id"] >= 1


@pytest.mark.asyncio
async def test_create_employee_duplicate_phone_returns_409(
    client: AsyncClient,
) -> None:
    await client.post(
        "/employees",
        json={"name": "First", "phone": "+1-555-0200"},
    )
    resp = await client.post(
        "/employees",
        json={"name": "Second", "phone": "+1-555-0200"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_employee_validation_empty_name(client: AsyncClient) -> None:
    resp = await client.post(
        "/employees",
        json={"name": "", "phone": "+1-555-0300"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_employees_includes_created(client: AsyncClient) -> None:
    await client.post(
        "/employees",
        json={"name": "Listed", "phone": "+1-555-0400"},
    )
    resp = await client.get("/employees")
    assert resp.status_code == 200
    items = resp.json()
    assert any(e["phone"] == "+1-555-0400" and e["name"] == "Listed" for e in items)


@pytest.mark.asyncio
async def test_get_employee_by_id(client: AsyncClient) -> None:
    created = (
        await client.post(
            "/employees",
            json={"name": "ById", "phone": "+1-555-0500"},
        )
    ).json()
    eid = created["id"]
    resp = await client.get(f"/employees/{eid}")
    assert resp.status_code == 200
    assert resp.json() == {"id": eid, "name": "ById", "phone": "+1-555-0500"}


@pytest.mark.asyncio
async def test_get_employee_missing_returns_404(client: AsyncClient) -> None:
    resp = await client.get("/employees/999999999")
    assert resp.status_code == 404
