from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, DateTime, Float, Integer, JSON, SmallInteger,
    String, Text, UniqueConstraint, func, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class Property(Base, TimestampMixin):
    __tablename__ = "properties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Source identifiers
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # domain_api | onthehouse
    url: Mapped[str] = mapped_column(Text, unique=True, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="for_sale")
    # for_sale | sold | withdrawn

    # Property type
    property_type: Mapped[Optional[str]] = mapped_column(String(30))
    # house | apartment | townhouse | land | rural

    # Address
    address_street: Mapped[Optional[str]] = mapped_column(String(200))
    address_suburb: Mapped[Optional[str]] = mapped_column(String(100))
    address_postcode: Mapped[Optional[str]] = mapped_column(String(4))
    suburb_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)

    # Geo
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)

    # Physical attributes
    land_size_sqm: Mapped[Optional[float]] = mapped_column(Float)
    floor_area_sqm: Mapped[Optional[float]] = mapped_column(Float)
    bedrooms: Mapped[Optional[int]] = mapped_column(SmallInteger)
    bathrooms: Mapped[Optional[int]] = mapped_column(SmallInteger)
    car_spaces: Mapped[Optional[int]] = mapped_column(SmallInteger)
    year_built: Mapped[Optional[int]] = mapped_column(SmallInteger)

    # Pricing (stored in AUD cents to avoid floating point)
    list_price: Mapped[Optional[int]] = mapped_column(BigInteger)
    price_guide_low: Mapped[Optional[int]] = mapped_column(BigInteger)
    price_guide_high: Mapped[Optional[int]] = mapped_column(BigInteger)

    # Sale data
    listed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sold_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    sold_price: Mapped[Optional[int]] = mapped_column(BigInteger)

    # Metadata
    description: Mapped[Optional[str]] = mapped_column(Text)
    features: Mapped[Optional[dict]] = mapped_column(JSON)  # ["pool", "aircon", ...]
    agent_name: Mapped[Optional[str]] = mapped_column(String(200))
    agency_name: Mapped[Optional[str]] = mapped_column(String(200))
    raw_json: Mapped[Optional[dict]] = mapped_column(JSON)

    # Tracking
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    suburb: Mapped[Optional["Suburb"]] = relationship(back_populates="properties", foreign_keys=[suburb_id])
    images: Mapped[list["PropertyImage"]] = relationship(
        back_populates="property", cascade="all, delete-orphan", order_by="PropertyImage.display_order"
    )
    valuations: Mapped[list["MLValuation"]] = relationship(
        back_populates="property", cascade="all, delete-orphan",
        order_by="MLValuation.predicted_at.desc()"
    )
    watchlist_items: Mapped[list["Watchlist"]] = relationship(
        back_populates="property", cascade="all, delete-orphan"
    )
    vg_record: Mapped[Optional["ValuerGeneralRecord"]] = relationship(
        back_populates="property", foreign_keys="ValuerGeneralRecord.property_id", uselist=False
    )

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_property_source_external"),
        Index("ix_properties_suburb_id", "suburb_id"),
        Index("ix_properties_status", "status"),
        Index("ix_properties_listed_at", "listed_at"),
        Index("ix_properties_latlong", "latitude", "longitude"),
    )

    def __repr__(self) -> str:
        return f"<Property {self.address_street}, {self.address_suburb}>"


class PropertyImage(Base):
    __tablename__ = "property_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(SmallInteger, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    property: Mapped["Property"] = relationship(back_populates="images", foreign_keys=[property_id])
