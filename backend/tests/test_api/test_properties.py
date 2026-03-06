import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_properties_empty(client: AsyncClient):
    resp = await client.get("/api/v1/properties")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
