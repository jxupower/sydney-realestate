"""FeatureBuilder — assembles XGBoost input vectors from the database.

Joins across: Property, SuburbStats, OsmAmenities, ValuerGeneralRecord.
Returns a pandas DataFrame with one row per property.
"""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Sequence

import numpy as np
import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.property import Property
from app.db.models.suburb import Suburb, SuburbStats
from app.db.models.osm import OsmAmenities
from app.db.models.valuer_general import ValuerGeneralRecord
from app.utils.geo import distance_to_cbd_km

# ── Constants ────────────────────────────────────────────────────────────────

SYDNEY_CBD_LAT = settings.sydney_cbd_lat
SYDNEY_CBD_LNG = settings.sydney_cbd_lng
CURRENT_YEAR = datetime.now().year
DEPRECIATION_RATE = 0.025   # ATO: 2.5%/yr straight-line
BUILDING_LIFE_YRS = 40

# Categorical columns (will be one-hot encoded)
CAT_COLS = ["property_type"]

# Numerical columns (will be imputed + scaled)
NUM_COLS = [
    "bedrooms",
    "bathrooms",
    "car_spaces",
    "land_size_sqm_log",
    "floor_area_sqm",
    "building_age_years",
    "building_depreciation_pct",
    "land_value_per_sqm",
    "improvement_value_cents",
    "improvement_to_land_ratio",
    "suburb_median_price",
    "capital_growth_3yr",
    "capital_growth_5yr",
    "rental_yield_pct",
    "distance_to_cbd_km",
    "nearest_train_km",
    "train_stations_2km",
    "nearest_bus_stop_km",
    "primary_schools_2km",
    "secondary_schools_3km",
    "supermarkets_1km",
    "parks_1km",
    "walkability_score",
]

ALL_FEATURE_COLS = CAT_COLS + NUM_COLS


# ── Helper ───────────────────────────────────────────────────────────────────

def _building_age(year_built: int | None) -> float | None:
    if year_built is None or year_built <= 0:
        return None
    return float(CURRENT_YEAR - year_built)


def _depreciation_pct(year_built: int | None) -> float | None:
    age = _building_age(year_built)
    if age is None:
        return None
    pct = min(age * DEPRECIATION_RATE, 1.0) * 100.0
    return round(pct, 2)


def _land_size_log(sqm: float | None) -> float | None:
    if sqm is None or sqm <= 0:
        return None
    return math.log1p(sqm)


def _improvement_to_land(imp: int | None, land: int | None) -> float | None:
    if not land or land == 0:
        return None
    imp = imp or 0
    return round(imp / land, 4)


def _land_value_per_sqm(land_cents: int | None, sqm: float | None) -> float | None:
    if not land_cents or not sqm or sqm <= 0:
        return None
    return round(land_cents / sqm, 2)


# ── FeatureBuilder ────────────────────────────────────────────────────────────

class FeatureBuilder:
    """Builds feature DataFrames for training and prediction."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def build_for_training(self, sold_since: date | None = None) -> pd.DataFrame:
        """Return rows for sold properties with a non-null sold_price.

        Adds a ``target_price_cents`` column for the training target.
        ``sold_since`` limits to sales on or after that date (default: 5 years ago)
        to keep the dataset in memory on modest hardware.
        """
        if sold_since is None:
            from datetime import timedelta
            sold_since = date.today().replace(year=date.today().year - 5)
        rows = await self._fetch_properties(
            status_filter="sold",
            require_sold_price=True,
            sold_since=sold_since,
        )
        df = self._to_dataframe(rows)
        return df

    async def build_for_prediction(self) -> pd.DataFrame:
        """Return rows for active for-sale properties."""
        rows = await self._fetch_properties(status_filter="for_sale", require_sold_price=False)
        return self._to_dataframe(rows)

    async def build_for_ids(self, property_ids: Sequence[int]) -> pd.DataFrame:
        """Build features for a specific list of property IDs."""
        rows = await self._fetch_properties(property_ids=property_ids)
        return self._to_dataframe(rows)

    # ── Internal ─────────────────────────────────────────────────────────────

    async def _fetch_properties(
        self,
        status_filter: str | None = None,
        require_sold_price: bool = False,
        property_ids: Sequence[int] | None = None,
        sold_since: date | None = None,
    ) -> list[dict]:
        """Execute a wide JOIN query and return a list of raw row dicts."""

        # Latest SuburbStats per suburb
        latest_stats_sq = (
            select(
                SuburbStats.suburb_id,
                SuburbStats.median_price.label("suburb_median_price"),
                SuburbStats.capital_growth_3yr,
                SuburbStats.capital_growth_5yr,
                SuburbStats.rental_yield_pct,
            )
            .distinct(SuburbStats.suburb_id)
            .order_by(SuburbStats.suburb_id, SuburbStats.snapshot_date.desc())
            .subquery("latest_stats")
        )

        stmt = (
            select(
                Property.id,
                Property.property_type,
                Property.bedrooms,
                Property.bathrooms,
                Property.car_spaces,
                Property.land_size_sqm,
                Property.floor_area_sqm,
                Property.year_built,
                Property.latitude,
                Property.longitude,
                Property.list_price,
                Property.sold_price,
                Property.sold_at,
                Property.suburb_id,
                # Suburb stats
                latest_stats_sq.c.suburb_median_price,
                latest_stats_sq.c.capital_growth_3yr,
                latest_stats_sq.c.capital_growth_5yr,
                latest_stats_sq.c.rental_yield_pct,
                # OSM
                OsmAmenities.nearest_train_km,
                OsmAmenities.train_stations_2km,
                OsmAmenities.nearest_bus_stop_km,
                OsmAmenities.primary_schools_2km,
                OsmAmenities.secondary_schools_3km,
                OsmAmenities.supermarkets_1km,
                OsmAmenities.parks_1km,
                OsmAmenities.walkability_score,
                # VG
                ValuerGeneralRecord.land_value_cents,
                ValuerGeneralRecord.improvement_value_cents,
                ValuerGeneralRecord.capital_value_cents,
            )
            .outerjoin(latest_stats_sq, latest_stats_sq.c.suburb_id == Property.suburb_id)
            .outerjoin(OsmAmenities, OsmAmenities.suburb_id == Property.suburb_id)
            .outerjoin(
                ValuerGeneralRecord,
                ValuerGeneralRecord.property_id == Property.id,
            )
        )

        if status_filter:
            stmt = stmt.where(Property.status == status_filter)
        if require_sold_price:
            stmt = stmt.where(
                Property.sold_price.is_not(None),
                Property.sold_at.is_not(None),
            )
        if property_ids:
            stmt = stmt.where(Property.id.in_(property_ids))
        if sold_since:
            stmt = stmt.where(Property.sold_at >= sold_since)

        result = await self.db.execute(stmt)
        return [dict(row._mapping) for row in result]

    def _to_dataframe(self, rows: list[dict]) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame(columns=["id"] + ALL_FEATURE_COLS + ["target_price_cents"])

        records = []
        for r in rows:
            land_sqm = r.get("land_size_sqm")
            land_cents = r.get("land_value_cents")
            imp_cents = r.get("improvement_value_cents")

            rec = {
                "id": r["id"],
                # categorical
                "property_type": r.get("property_type") or "house",
                # numerical
                "bedrooms": r.get("bedrooms"),
                "bathrooms": r.get("bathrooms"),
                "car_spaces": r.get("car_spaces"),
                "land_size_sqm_log": _land_size_log(land_sqm),
                "floor_area_sqm": r.get("floor_area_sqm"),
                "building_age_years": _building_age(r.get("year_built")),
                "building_depreciation_pct": _depreciation_pct(r.get("year_built")),
                "land_value_per_sqm": _land_value_per_sqm(land_cents, land_sqm),
                "improvement_value_cents": imp_cents,
                "improvement_to_land_ratio": _improvement_to_land(imp_cents, land_cents),
                "suburb_median_price": r.get("suburb_median_price"),
                "capital_growth_3yr": r.get("capital_growth_3yr"),
                "capital_growth_5yr": r.get("capital_growth_5yr"),
                "rental_yield_pct": r.get("rental_yield_pct"),
                "distance_to_cbd_km": (
                    distance_to_cbd_km(r.get("latitude"), r.get("longitude"))
                    if r.get("latitude") and r.get("longitude")
                    else None
                ),
                "nearest_train_km": r.get("nearest_train_km"),
                "train_stations_2km": r.get("train_stations_2km"),
                "nearest_bus_stop_km": r.get("nearest_bus_stop_km"),
                "primary_schools_2km": r.get("primary_schools_2km"),
                "secondary_schools_3km": r.get("secondary_schools_3km"),
                "supermarkets_1km": r.get("supermarkets_1km"),
                "parks_1km": r.get("parks_1km"),
                "walkability_score": r.get("walkability_score"),
                # target (only populated for sold properties)
                "target_price_cents": r.get("sold_price"),
                "list_price_cents": r.get("list_price"),
                "sold_at": r.get("sold_at"),
            }
            records.append(rec)

        df = pd.DataFrame(records)

        # Ensure proper dtypes for numerical columns
        for col in NUM_COLS:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df
