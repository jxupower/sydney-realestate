import pytest
from httpx import AsyncClient


ADMIN_KEY = "test-admin-key"
ADMIN_HEADERS = {"X-Admin-Key": ADMIN_KEY}


@pytest.fixture(autouse=True)
def set_admin_key(monkeypatch):
    """Override ADMIN_API_KEY setting for all tests in this module."""
    import app.config as cfg
    monkeypatch.setattr(cfg.settings, "admin_api_key", ADMIN_KEY)


@pytest.mark.asyncio
async def test_ingestion_runs_empty(client: AsyncClient):
    resp = await client.get("/api/v1/admin/ingestion-runs", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_admin_requires_key(client: AsyncClient):
    resp = await client.get("/api/v1/admin/ingestion-runs")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_wrong_key(client: AsyncClient):
    resp = await client.get(
        "/api/v1/admin/ingestion-runs",
        headers={"X-Admin-Key": "wrong-key"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_clear_cache(client: AsyncClient):
    resp = await client.delete("/api/v1/admin/cache?pattern=test:*", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["pattern"] == "test:*"
