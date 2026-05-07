import pytest
from httpx import AsyncClient


async def _create_employee(client: AsyncClient, suffix: str) -> dict:
    return (
        await client.post(
            "/employees",
            json={"name": f"Emp{suffix}", "phone": f"+1-555-1{suffix}00"},
        )
    ).json()


async def _create_service(client: AsyncClient, suffix: str) -> dict:
    return (
        await client.post(
            "/services",
            json={"name": f"Svc{suffix}", "duration_minutes": 30, "price": "20.00"},
        )
    ).json()


@pytest.mark.asyncio
async def test_employee_services_create_and_list_filter(client: AsyncClient) -> None:
    employee = await _create_employee(client, "01")
    service = await _create_service(client, "01")

    create_resp = await client.post(
        "/employee-services",
        json={"employee_id": employee["id"], "service_id": service["id"]},
    )
    assert create_resp.status_code == 201
    created = create_resp.json()

    list_resp = await client.get("/employee-services")
    assert list_resp.status_code == 200
    assert any(item["id"] == created["id"] for item in list_resp.json())

    filtered_resp = await client.get(f"/employee-services?employee_id={employee['id']}")
    assert filtered_resp.status_code == 200
    assert all(item["employee_id"] == employee["id"] for item in filtered_resp.json())


@pytest.mark.asyncio
async def test_employee_services_duplicate_returns_409(client: AsyncClient) -> None:
    employee = await _create_employee(client, "02")
    service = await _create_service(client, "02")
    payload = {"employee_id": employee["id"], "service_id": service["id"]}
    assert (await client.post("/employee-services", json=payload)).status_code == 201
    resp = await client.post("/employee-services", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_employee_services_missing_refs_return_404(client: AsyncClient) -> None:
    service = await _create_service(client, "03")
    resp_employee = await client.post(
        "/employee-services",
        json={"employee_id": 99999999, "service_id": service["id"]},
    )
    assert resp_employee.status_code == 404

    employee = await _create_employee(client, "03")
    resp_service = await client.post(
        "/employee-services",
        json={"employee_id": employee["id"], "service_id": 99999999},
    )
    assert resp_service.status_code == 404


@pytest.mark.asyncio
async def test_employee_services_get_delete(client: AsyncClient) -> None:
    employee = await _create_employee(client, "04")
    service = await _create_service(client, "04")
    created = (
        await client.post(
            "/employee-services",
            json={"employee_id": employee["id"], "service_id": service["id"]},
        )
    ).json()

    get_resp = await client.get(f"/employee-services/{created['id']}")
    assert get_resp.status_code == 200

    delete_resp = await client.delete(f"/employee-services/{created['id']}")
    assert delete_resp.status_code == 204

    assert (await client.get(f"/employee-services/{created['id']}")).status_code == 404
    assert (await client.delete("/employee-services/99999999")).status_code == 404
