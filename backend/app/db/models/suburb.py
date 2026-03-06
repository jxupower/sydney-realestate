from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, Integer, SmallInteger, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base, TimestampMixin


class Suburb(Base, TimestampMixin):
    __tablename__ = "suburbs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    postcode: Mapped[str] = mapped_column(String(4), nullable=False)
    lga: Mapped[Optional[str]] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(3), default="NSW")
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)
    boundary_geojson: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    properties: Mapped[list["Property"]] = relationship(back_populates="suburb", lazy="select")
    stats: Mapped[list["SuburbStats"]] = relationship(
        back_populates="suburb", order_by="SuburbStats.snapshot_date.desc()", lazy="select"
    )
    osm_amenities: Mapped[Optional["OsmAmenities"]] = relationship(back_populates="suburb", uselist=False)

    __table_args__ = (UniqueConstraint("name", "postcode", name="uq_suburb_name_postcode"),)

    def __repr__(self) -> str:
        return f"<Suburb {self.name} {self.postcode}>"


class SuburbStats(Base):
    __tablename__ = "suburb_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suburb_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    median_price: Mapped[Optional[int]] = mapped_column(Integer)  # AUD cents
    median_price_house: Mapped[Optional[int]] = mapped_column(Integer)
    median_price_unit: Mapped[Optional[int]] = mapped_column(Integer)
    rental_yield_pct: Mapped[Optional[float]] = mapped_column(Float)
    capital_growth_1yr: Mapped[Optional[float]] = mapped_column(Float)
    capital_growth_3yr: Mapped[Optional[float]] = mapped_column(Float)
    capital_growth_5yr: Mapped[Optional[float]] = mapped_column(Float)
    capital_growth_10yr: Mapped[Optional[float]] = mapped_column(Float)
    days_on_market_median: Mapped[Optional[int]] = mapped_column(SmallInteger)
    clearance_rate_pct: Mapped[Optional[float]] = mapped_column(Float)
    total_listings: Mapped[Optional[int]] = mapped_column(Integer)
    source: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship
    suburb: Mapped["Suburb"] = relationship(back_populates="stats", foreign_keys=[suburb_id])

    __table_args__ = (
        UniqueConstraint("suburb_id", "snapshot_date", name="uq_suburb_stats_date"),
    )
