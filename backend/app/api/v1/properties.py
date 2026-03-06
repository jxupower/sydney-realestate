from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.repositories.property_repo import PropertyRepository
from app.schemas.property import PropertyListResponse, PropertyDetail

router = APIRouter()


@router.get("", response_model=PropertyListResponse)
async def list_properties(
    suburb: Optional[str] = None,
    postcode: Optional[str] = None,
    property_type: Optional[str] = None,
    bedrooms_min: Optional[int] = None,
    bedrooms_max: Optional[int] = None,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    land_size_min: Optional[float] = None,
    land_size_max: Optional[float] = None,
    underval_score_min: Optional[float] = None,
    status: Optional[str] = "for_sale",
    # Map viewport bbox: sw_lat,sw_lng,ne_lat,ne_lng
    bbox: Optional[str] = None,
    sort_by: str = Query(default="underval_score", pattern="^(underval_score|price|listed_at|suburb)$"),
    sort_dir: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    repo = PropertyRepository(db)
    items, total = await repo.list_with_valuations(
        suburb=suburb,
        postcode=postcode,
        property_type=property_type,
        bedrooms_min=bedrooms_min,
        bedrooms_max=bedrooms_max,
        price_min=price_min,
        price_max=price_max,
        land_size_min=land_size_min,
        land_size_max=land_size_max,
        underval_score_min=underval_score_min,
        status=status,
        bbox=bbox,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
    return PropertyListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/undervalued", response_model=PropertyListResponse)
async def top_undervalued(
    limit: int = Query(default=30, le=100),
    property_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    repo = PropertyRepository(db)
    items, total = await repo.list_with_valuations(
        status="for_sale",
        underval_score_min=5.0,
        sort_by="underval_score",
        sort_dir="desc",
        property_type=property_type,
        limit=limit,
        offset=0,
    )
    return PropertyListResponse(items=items, total=total, limit=limit, offset=0)


@router.get("/{property_id}", response_model=PropertyDetail)
async def get_property(property_id: int, db: AsyncSession = Depends(get_db)):
    repo = PropertyRepository(db)
    return await repo.get_detail(property_id)


@router.get("/{property_id}/valuation")
async def get_valuation(property_id: int, db: AsyncSession = Depends(get_db)):
    repo = PropertyRepository(db)
    return await repo.get_latest_valuation(property_id)
