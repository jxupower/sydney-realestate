"""Base ingester ABC and shared RawProperty dataclass."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RawProperty:
    """Normalised property data from any ingestion source."""
    external_id: str
    source: str
    url: str
    status: str  # for_sale | sold | withdrawn

    # Property type
    property_type: Optional[str] = None  # house | apartment | townhouse | land

    # Address
    address_street: Optional[str] = None
    address_suburb: Optional[str] = None
    address_postcode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Physical
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    car_spaces: Optional[int] = None
    land_size_sqm: Optional[float] = None
    floor_area_sqm: Optional[float] = None
    year_built: Optional[int] = None

    # Pricing (AUD cents)
    list_price: Optional[int] = None
    price_guide_low: Optional[int] = None
    price_guide_high: Optional[int] = None

    # Sale info
    listed_at: Optional[datetime] = None
    sold_at: Optional[datetime] = None
    sold_price: Optional[int] = None

    # Meta
    description: Optional[str] = None
    features: list = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    agent_name: Optional[str] = None
    agency_name: Optional[str] = None
    raw_json: dict = field(default_factory=dict)

    def to_db_dict(self) -> dict:
        """Convert to a dict suitable for Property model upsert."""
        return {
            "external_id": self.external_id,
            "source": self.source,
            "url": self.url,
            "status": self.status,
            "property_type": self.property_type,
            "address_street": self.address_street,
            "address_suburb": self.address_suburb,
            "address_postcode": self.address_postcode,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "car_spaces": self.car_spaces,
            "land_size_sqm": self.land_size_sqm,
            "floor_area_sqm": self.floor_area_sqm,
            "year_built": self.year_built,
            "list_price": self.list_price,
            "price_guide_low": self.price_guide_low,
            "price_guide_high": self.price_guide_high,
            "listed_at": self.listed_at,
            "sold_at": self.sold_at,
            "sold_price": self.sold_price,
            "description": self.description,
            "features": self.features,
            "agent_name": self.agent_name,
            "agency_name": self.agency_name,
            "raw_json": self.raw_json,
        }


class BaseIngester(ABC):
    """Abstract base class for all data ingesters."""

    def is_available(self) -> bool:
        """Return False to disable this ingester (e.g. missing API key)."""
        return True

    @abstractmethod
    async def fetch(self) -> list[RawProperty]:
        """Fetch and normalise raw property data from the source."""
        ...
