from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint, func, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base


class MLValuation(Base):
    __tablename__ = "ml_valuations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[int] = mapped_column(ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # Predicted fair value (AUD cents)
    predicted_value_cents: Mapped[Optional[int]] = mapped_column(BigInteger)
    confidence_interval_low: Mapped[Optional[int]] = mapped_column(BigInteger)
    confidence_interval_high: Mapped[Optional[int]] = mapped_column(BigInteger)

    # Core metric: (predicted - list_price) / predicted * 100
    # Positive = undervalued, negative = overvalued
    underval_score_pct: Mapped[Optional[float]] = mapped_column(Float, index=True)

    # SHAP feature importances per prediction {feature_name: shap_value}
    feature_importances: Mapped[Optional[dict]] = mapped_column(JSON)

    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    property: Mapped["Property"] = relationship(back_populates="valuations", foreign_keys=[property_id])

    __table_args__ = (
        UniqueConstraint("property_id", "model_version", name="uq_valuation_property_version"),
        Index("ix_ml_valuations_score_desc", "underval_score_pct"),
    )
