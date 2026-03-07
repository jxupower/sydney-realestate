import pytest
from httpx import AsyncClient

from app.db.models.suburb import Suburb, SuburbStats
import datetime


async def _create_suburb(db_session, **overrides) -> Suburb:
    defaults = dict(
        name="Bondi",
        postcode="2026",
        state="NSW",
        lga="Waverley",
        latitude=-33.89,
        longitude=151.27,
    )
    defaults.update(overrides)
    suburb = Suburb(**defaults)
    db_session.add(suburb)
    await db_session.flush()
    await db_session.refresh(suburb)
    return suburb


async def _create_stats(db_session, suburb_id: int, **overrides) -> SuburbStats:
    defaults = dict(
        suburb_id=suburb_id,
        snapshot_date=datetime.date(2025, 1, 1),
        median_price=200000000,
        capital_growth_3yr=15.5,
        rental_yield_pct=3.2,
    )
    defaults.update(overrides)
    stats = SuburbStats(**defaults)
    db_session.add(stats)
    await db_session.flush()
    return stats


# ── GET /suburbs ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_suburbs_empty(client: AsyncClient):
    resp = await client.get("/api/v1/suburbs")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_suburbs_returns_items(client: AsyncClient, db_session):
    suburb = await _create_suburb(db_session)
    await _create_stats(db_session, suburb.id)
    await db_session.commit()

    resp = await client.get("/api/v1/suburbs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["name"] == "Bondi"
    assert item["postcode"] == "2026"
    assert item["stats"]["median_price"] == 200_000_000


@pytest.mark.asyncio
async def test_list_suburbs_filter_by_postcode(client: AsyncClient, db_session):
    s1 = await _create_suburb(db_session, name="Bondi", postcode="2026")
    s2 = await _create_suburb(db_session, name="Manly", postcode="2095")
    await db_session.commit()

    resp = await client.get("/api/v1/suburbs?postcode=2026")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["postcode"] == "2026"


@pytest.mark.asyncio
async def test_list_suburbs_filter_by_lga(client: AsyncClient, db_session):
    await _create_suburb(db_session, name="Bondi", postcode="2026", lga="Waverley")
    await _create_suburb(db_session, name="Manly", postcode="2095", lga="Northern Beaches")
    await db_session.commit()

    resp = await client.get("/api/v1/suburbs?lga=Waverley")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Bondi"


# ── GET /suburbs/map ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_suburbs_geojson(client: AsyncClient, db_session):
    await _create_suburb(db_session)
    await db_session.commit()

    resp = await client.get("/api/v1/suburbs/map")
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "FeatureCollection"
    assert isinstance(data["features"], list)
    assert len(data["features"]) == 1
    feat = data["features"][0]
    assert feat["type"] == "Feature"
    assert "geometry" in feat
    assert feat["geometry"]["type"] == "Point"


# ── GET /suburbs/{id} ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_suburb_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/suburbs/9999999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_suburb_detail(client: AsyncClient, db_session):
    suburb = await _create_suburb(db_session)
    await _create_stats(db_session, suburb.id)
    await db_session.commit()

    resp = await client.get(f"/api/v1/suburbs/{suburb.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == suburb.id
    assert data["name"] == "Bondi"
    assert "stats" in data
    assert "stats_history" in data
    assert len(data["stats_history"]) == 1


# ── GET /suburbs/{id}/stats ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_suburb_stats_history(client: AsyncClient, db_session):
    suburb = await _create_suburb(db_session, name="Newtown", postcode="2042")
    for i, year in enumerate([2023, 2024, 2025]):
        await _create_stats(
            db_session, suburb.id,
            snapshot_date=datetime.date(year, 1, 1),
            median_price=(100 + i * 10) * 100_000_00,
        )
    await db_session.commit()

    resp = await client.get(f"/api/v1/suburbs/{suburb.id}/stats")
    assert resp.status_code == 200
    history = resp.json()
    assert len(history) == 3
    # Should be ordered oldest → newest
    dates = [h["snapshot_date"] for h in history]
    assert dates == sorted(dates)
