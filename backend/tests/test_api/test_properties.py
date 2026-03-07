import pytest
from httpx import AsyncClient

from app.db.models.property import Property
from app.db.models.suburb import Suburb


async def _create_suburb(db_session) -> Suburb:
    suburb = Suburb(name="Bondi", postcode="2026", state="NSW", latitude=-33.89, longitude=151.27)
    db_session.add(suburb)
    await db_session.flush()
    await db_session.refresh(suburb)
    return suburb


async def _create_property(db_session, suburb_id: int | None = None, **overrides) -> Property:
    defaults = dict(
        external_id="TEST001",
        source="domain_api",
        url="https://domain.com.au/test/1",
        status="for_sale",
        property_type="house",
        address_street="1 Test St",
        address_suburb="Bondi",
        address_postcode="2026",
        suburb_id=suburb_id,
        latitude=-33.89,
        longitude=151.27,
        bedrooms=3,
        bathrooms=2,
        car_spaces=1,
        list_price=150000000,  # $1.5M in cents
    )
    defaults.update(overrides)
    prop = Property(**defaults)
    db_session.add(prop)
    await db_session.flush()
    await db_session.refresh(prop)
    return prop


# ── GET /properties ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_properties_empty(client: AsyncClient):
    resp = await client.get("/api/v1/properties")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_properties_returns_items(client: AsyncClient, db_session):
    await _create_property(db_session)
    await db_session.commit()

    resp = await client.get("/api/v1/properties")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["address_suburb"] == "Bondi"
    assert item["list_price"] == 1_500_000


@pytest.mark.asyncio
async def test_list_properties_filter_by_suburb(client: AsyncClient, db_session):
    await _create_property(db_session, address_suburb="Bondi", external_id="A1")
    await _create_property(
        db_session,
        address_suburb="Manly",
        external_id="A2",
        url="https://domain.com.au/test/2",
    )
    await db_session.commit()

    resp = await client.get("/api/v1/properties?suburb=Bondi")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["address_suburb"] == "Bondi"


@pytest.mark.asyncio
async def test_list_properties_filter_by_bedrooms(client: AsyncClient, db_session):
    await _create_property(db_session, bedrooms=2, external_id="B1", url="https://domain.com.au/b/1")
    await _create_property(db_session, bedrooms=4, external_id="B2", url="https://domain.com.au/b/2")
    await db_session.commit()

    resp = await client.get("/api/v1/properties?bedrooms_min=3")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["bedrooms"] == 4


@pytest.mark.asyncio
async def test_list_properties_filter_by_price(client: AsyncClient, db_session):
    await _create_property(db_session, list_price=100000000, external_id="P1", url="https://d.com/p/1")  # $1M
    await _create_property(db_session, list_price=200000000, external_id="P2", url="https://d.com/p/2")  # $2M
    await db_session.commit()

    resp = await client.get("/api/v1/properties?price_max=1500000")  # $1.5M cap
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_properties_bbox_filter(client: AsyncClient, db_session):
    # Inside bbox
    await _create_property(db_session, latitude=-33.89, longitude=151.27, external_id="G1", url="https://d.com/g/1")
    # Outside bbox
    await _create_property(db_session, latitude=-34.5, longitude=150.5, external_id="G2", url="https://d.com/g/2")
    await db_session.commit()

    bbox = "-34.0,151.0,-33.8,151.5"
    resp = await client.get(f"/api/v1/properties?bbox={bbox}")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_properties_pagination(client: AsyncClient, db_session):
    for i in range(5):
        await _create_property(
            db_session,
            external_id=f"PAG{i}",
            url=f"https://domain.com.au/pag/{i}",
        )
    await db_session.commit()

    resp = await client.get("/api/v1/properties?limit=2&offset=0")
    data = resp.json()
    assert data["total"] == 5
    assert len(data["items"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_list_properties_sort_by_price(client: AsyncClient, db_session):
    await _create_property(db_session, list_price=100000000, external_id="S1", url="https://d.com/s/1")
    await _create_property(db_session, list_price=300000000, external_id="S2", url="https://d.com/s/2")
    await db_session.commit()

    resp = await client.get("/api/v1/properties?sort_by=price&sort_dir=asc")
    data = resp.json()
    assert data["items"][0]["list_price"] == 1_000_000
    assert data["items"][1]["list_price"] == 3_000_000


# ── GET /properties/{id} ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_property_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/properties/9999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_property_detail(client: AsyncClient, db_session):
    prop = await _create_property(db_session, external_id="DET1", url="https://d.com/det/1")
    await db_session.commit()

    resp = await client.get(f"/api/v1/properties/{prop.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == prop.id
    assert data["status"] == "for_sale"
    assert data["list_price"] == 1_500_000
    assert "valuation" in data
    assert "images" in data


# ── GET /properties/{id}/valuation ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_valuation_no_prediction(client: AsyncClient, db_session):
    prop = await _create_property(db_session, external_id="VAL1", url="https://d.com/val/1")
    await db_session.commit()

    resp = await client.get(f"/api/v1/properties/{prop.id}/valuation")
    assert resp.status_code == 200
    assert resp.json() is None


# ── GET /health ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
