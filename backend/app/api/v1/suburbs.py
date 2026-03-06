from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.suburb_repo import SuburbRepository

router = APIRouter()


@router.get("")
async def list_suburbs(
    lga: Optional[str] = None,
    postcode: Optional[str] = None,
    sort_by: str = Query(default="median_price", pattern="^(median_price|capital_growth_3yr|rental_yield_pct)$"),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    repo = SuburbRepository(db)
    return await repo.list_with_stats(lga=lga, postcode=postcode, sort_by=sort_by, limit=limit, offset=offset)


@router.get("/map")
async def suburbs_geojson(db: AsyncSession = Depends(get_db)):
    """Lightweight GeoJSON for choropleth layer — suburb polygons + key metric."""
    repo = SuburbRepository(db)
    return await repo.get_geojson()


@router.get("/{suburb_id}")
async def get_suburb(suburb_id: int, db: AsyncSession = Depends(get_db)):
    repo = SuburbRepository(db)
    return await repo.get_by_id(suburb_id)


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
    repo = PropertyRepository(db)
    items, total = await repo.list_with_valuations(
        suburb_id=suburb_id, status="for_sale", sort_by="underval_score",
        sort_dir="desc", limit=limit, offset=offset,
    )
    from app.schemas.property import PropertyListResponse
    return PropertyListResponse(items=items, total=total, limit=limit, offset=offset)
