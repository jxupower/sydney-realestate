import pytest
from httpx import AsyncClient

from app.db.models.property import Property


async def _create_property(db_session, **overrides) -> Property:
    defaults = dict(
        external_id="WL001",
        source="domain_api",
        url="https://domain.com.au/wl/1",
        status="for_sale",
        property_type="house",
        address_street="1 Test St",
        address_suburb="Bondi",
        address_postcode="2026",
        list_price=120000000,
    )
    defaults.update(overrides)
    prop = Property(**defaults)
    db_session.add(prop)
    await db_session.flush()
    await db_session.refresh(prop)
    return prop


SESSION_ID = "test-session-uuid-12345"
HEADERS = {"X-Session-ID": SESSION_ID}


# ── GET /watchlist ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_watchlist_empty(client: AsyncClient):
    resp = await client.get("/api/v1/watchlist", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_watchlist_no_session(client: AsyncClient):
    resp = await client.get("/api/v1/watchlist")
    assert resp.status_code == 200
    assert resp.json() == []


# ── POST /watchlist ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_to_watchlist(client: AsyncClient, db_session):
    prop = await _create_property(db_session)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/watchlist",
        json={"property_id": prop.id, "notes": "Great location"},
        headers=HEADERS,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["property_id"] == prop.id
    assert data["notes"] == "Great location"


@pytest.mark.asyncio
async def test_add_to_watchlist_no_session(client: AsyncClient, db_session):
    prop = await _create_property(db_session, external_id="WL002", url="https://d.com/wl/2")
    await db_session.commit()

    resp = await client.post("/api/v1/watchlist", json={"property_id": prop.id})
    assert resp.status_code == 400


# ── GET /watchlist after add ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_watchlist_roundtrip(client: AsyncClient, db_session):
    prop = await _create_property(db_session, external_id="WL003", url="https://d.com/wl/3")
    await db_session.commit()

    # Add
    add_resp = await client.post(
        "/api/v1/watchlist",
        json={"property_id": prop.id},
        headers=HEADERS,
    )
    assert add_resp.status_code == 201

    # Get
    get_resp = await client.get("/api/v1/watchlist", headers=HEADERS)
    assert get_resp.status_code == 200
    items = get_resp.json()
    assert len(items) == 1
    assert items[0]["property_id"] == prop.id


# ── DELETE /watchlist/{property_id} ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_remove_from_watchlist(client: AsyncClient, db_session):
    prop = await _create_property(db_session, external_id="WL004", url="https://d.com/wl/4")
    await db_session.commit()

    # Add
    await client.post(
        "/api/v1/watchlist",
        json={"property_id": prop.id},
        headers=HEADERS,
    )

    # Remove
    del_resp = await client.delete(f"/api/v1/watchlist/{prop.id}", headers=HEADERS)
    assert del_resp.status_code == 204

    # Verify gone
    get_resp = await client.get("/api/v1/watchlist", headers=HEADERS)
    assert get_resp.json() == []


# ── PATCH /watchlist/{property_id} ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_watchlist_notes(client: AsyncClient, db_session):
    prop = await _create_property(db_session, external_id="WL005", url="https://d.com/wl/5")
    await db_session.commit()

    await client.post(
        "/api/v1/watchlist",
        json={"property_id": prop.id, "notes": "Original"},
        headers=HEADERS,
    )

    patch_resp = await client.patch(
        f"/api/v1/watchlist/{prop.id}",
        json={"notes": "Updated note"},
        headers=HEADERS,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["notes"] == "Updated note"
