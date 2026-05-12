import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_services_crud(client: AsyncClient) -> None:
    create_resp = await client.post(
        "/services",
        json={"name": "Haircut", "duration_minutes": 45, "price": "25.00"},
    )
    assert create_resp.status_code == 201
    created = create_resp.json()

    get_resp = await client.get(f"/services/{created['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "Haircut"

    patch_resp = await client.patch(
        f"/services/{created['id']}",
        json={"price": "30.00"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["price"] == "30.00"

    list_resp = await client.get("/services")
    assert list_resp.status_code == 200
    assert any(item["id"] == created["id"] for item in list_resp.json())

    delete_resp = await client.delete(f"/services/{created['id']}")
    assert delete_resp.status_code == 204
    missing_resp = await client.get(f"/services/{created['id']}")
    assert missing_resp.status_code == 404


@pytest.mark.asyncio
async def test_service_validation(client: AsyncClient) -> None:
    resp_negative_price = await client.post(
        "/services",
        json={"name": "Color", "duration_minutes": 30, "price": "-1.00"},
    )
    assert resp_negative_price.status_code == 422

    resp_zero_duration = await client.post(
        "/services",
        json={"name": "Color", "duration_minutes": 0, "price": "10.00"},
    )
    assert resp_zero_duration.status_code == 422


@pytest.mark.asyncio
async def test_service_missing_returns_404(client: AsyncClient) -> None:
    assert (await client.get("/services/999999999")).status_code == 404
    assert (await client.patch("/services/999999999", json={"name": "X"})).status_code == 404
    assert (await client.delete("/services/999999999")).status_code == 404
