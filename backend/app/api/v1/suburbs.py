from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.suburb_repo import SuburbRepository
from app.utils.cache import cache_get, cache_set, make_cache_key

router = APIRouter()

# Cache TTLs
_TTL_LIST = 300       # 5 min — suburb list
_TTL_GEOJSON = 900    # 15 min — GeoJSON choropleth
_TTL_DETAIL = 300     # 5 min — single suburb


@router.get("")
async def list_suburbs(
    lga: Optional[str] = None,
    postcode: Optional[str] = None,
    sort_by: str = Query(default="median_price", pattern="^(median_price|capital_growth_3yr|rental_yield_pct)$"),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    key = make_cache_key("suburbs:list", lga, postcode, sort_by, limit, offset)
    cached = await cache_get(key)
    if cached is not None:
        return cached

    repo = SuburbRepository(db)
    result = await repo.list_with_stats(lga=lga, postcode=postcode, sort_by=sort_by, limit=limit, offset=offset)
    await cache_set(key, result, ttl_seconds=_TTL_LIST)
    return result


@router.get("/map")
async def suburbs_geojson(db: AsyncSession = Depends(get_db)):
    """Lightweight GeoJSON for choropleth layer — suburb polygons + key metrics."""
    key = "suburbs:geojson"
    cached = await cache_get(key)
    if cached is not None:
        return cached

    repo = SuburbRepository(db)
    result = await repo.get_geojson()
    await cache_set(key, result, ttl_seconds=_TTL_GEOJSON)
    return result


@router.get("/{suburb_id}")
async def get_suburb(suburb_id: int, db: AsyncSession = Depends(get_db)):
    key = make_cache_key("suburbs:detail", suburb_id)
    cached = await cache_get(key)
    if cached is not None:
        return cached

    repo = SuburbRepository(db)
    result = await repo.get_detail(suburb_id)
    await cache_set(key, result, ttl_seconds=_TTL_DETAIL)
    return result


@router.get("/{suburb_id}/stats")
async def suburb_stats_history(suburb_id: int, db: AsyncSession = Depends(get_db)):
    """Historical stat snapshots for trend charts."""
    repo = SuburbRepository(db)
    return await repo.get_stats_history(suburb_id)


@router.get("/{suburb_id}/properties")
async def suburb_properties(
    suburb_id: int,
    limit: int = Query(default=20, le=50),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    from app.repositories.property_repo import PropertyRepository
    from app.schemas.property import PropertyListResponse
    repo = PropertyRepository(db)
    items, total = await repo.list_with_valuations(
        suburb_id=suburb_id, status="for_sale", sort_by="underval_score",
        sort_dir="desc", limit=limit, offset=offset,
    )
    return PropertyListResponse(items=items, total=total, limit=limit, offset=offset)
