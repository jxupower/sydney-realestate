from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class OsmAmenities(Base):
    """Pre-fetched OpenStreetMap amenity data per suburb — refreshed monthly."""

    __tablename__ = "osm_amenities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    suburb_id: Mapped[int] = mapped_column(ForeignKey("suburbs.id", ondelete="CASCADE"), nullable=False, index=True)

    # Transport distances (km)
    nearest_train_km: Mapped[Optional[float]] = mapped_column(Float)
    nearest_bus_stop_km: Mapped[Optional[float]] = mapped_column(Float)

    # Counts within radius
    train_stations_2km: Mapped[Optional[int]] = mapped_column(Integer)
    bus_stops_500m: Mapped[Optional[int]] = mapped_column(Integer)
    primary_schools_2km: Mapped[Optional[int]] = mapped_column(Integer)
    secondary_schools_3km: Mapped[Optional[int]] = mapped_column(Integer)
    supermarkets_1km: Mapped[Optional[int]] = mapped_column(Integer)
    parks_1km: Mapped[Optional[int]] = mapped_column(Integer)

    # Composite walkability score 0–100
    walkability_score: Mapped[Optional[float]] = mapped_column(Float)

    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    suburb: Mapped["Suburb"] = relationship(back_populates="osm_amenities", foreign_keys=[suburb_id])

    __table_args__ = (
        UniqueConstraint("suburb_id", name="uq_osm_suburb"),
    )
