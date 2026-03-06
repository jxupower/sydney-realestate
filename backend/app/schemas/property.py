from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ValuationSummary(BaseModel):
    predicted_value: Optional[int] = None
    underval_score_pct: Optional[float] = None
    model_version: Optional[str] = None


class PropertySummary(BaseModel):
    id: int
    source: str
    url: str
    status: str
    property_type: Optional[str] = None
    address: Optional[str] = None
    address_suburb: Optional[str] = None
    address_postcode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    car_spaces: Optional[int] = None
    land_size_sqm: Optional[float] = None
    list_price: Optional[int] = None  # AUD dollars
    listed_at: Optional[datetime] = None
    valuation: Optional[ValuationSummary] = None

    model_config = {"from_attributes": True}


class PropertyListResponse(BaseModel):
    items: list[dict]
    total: int
    limit: int
    offset: int


class PropertyDetail(BaseModel):
    id: int
    source: str
    url: str
    status: str
    property_type: Optional[str] = None
    address_street: Optional[str] = None
    address_suburb: Optional[str] = None
    address_postcode: Optional[str] = None
    suburb_id: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    land_size_sqm: Optional[float] = None
    floor_area_sqm: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    car_spaces: Optional[int] = None
    year_built: Optional[int] = None
    list_price: Optional[int] = None
    price_guide_low: Optional[int] = None
    price_guide_high: Optional[int] = None
    listed_at: Optional[datetime] = None
    sold_at: Optional[datetime] = None
    sold_price: Optional[int] = None
    description: Optional[str] = None
    features: Optional[list] = None
    agent_name: Optional[str] = None
    agency_name: Optional[str] = None
    images: Optional[list[str]] = None
    valuation: Optional[dict] = None

    model_config = {"from_attributes": True}
