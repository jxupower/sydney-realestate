from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class ValuerGeneralRecord(Base):
    __tablename__ = "valuer_general_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Legal parcel identifier from VG data
    lot_plan: Mapped[Optional[str]] = mapped_column(String(50), index=True)

    # Address fields from VG CSV
    address_street: Mapped[Optional[str]] = mapped_column(String(200))
    address_suburb: Mapped[Optional[str]] = mapped_column(String(100))
    address_postcode: Mapped[Optional[str]] = mapped_column(String(4))
    lga: Mapped[Optional[str]] = mapped_column(String(100))

    # Valuation figures (AUD cents)
    land_value_cents: Mapped[Optional[int]] = mapped_column(BigInteger)
    capital_value_cents: Mapped[Optional[int]] = mapped_column(BigInteger)  # land + improvements
    improvement_value_cents: Mapped[Optional[int]] = mapped_column(BigInteger)  # derived

    # VG valuation date
    base_date: Mapped[Optional[date]] = mapped_column(Date)

    # Linked to a property row after fuzzy address matching (nullable until matched)
    property_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationship (nullable)
    property: Mapped[Optional["Property"]] = relationship(
        back_populates="vg_record", foreign_keys=[property_id]
    )

    __table_args__ = (
        UniqueConstraint("lot_plan", "base_date", name="uq_vg_lot_plan_date"),
    )
