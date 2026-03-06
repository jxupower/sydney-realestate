from typing import Optional

from fastapi import HTTPException
from sqlalchemy import desc, func, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.property import Property
from app.db.models.valuation import MLValuation
from app.repositories.base import BaseRepository


class PropertyRepository(BaseRepository[Property]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Property)

    async def get_by_source(self, source: str, external_id: str) -> Optional[Property]:
        result = await self.db.execute(
            select(Property).where(
                Property.source == source,
                Property.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(self, data: dict) -> tuple[Property, bool]:
        """Insert or update a property. Returns (property, was_inserted)."""
        existing = await self.get_by_source(data["source"], data["external_id"])
        if existing:
            for key, value in data.items():
                if key not in ("source", "external_id", "first_seen_at"):
                    setattr(existing, key, value)
            existing.last_seen_at = func.now()
            await self.db.flush()
            return existing, False
        else:
            prop = Property(**data)
            self.db.add(prop)
            await self.db.flush()
            await self.db.refresh(prop)
            return prop, True

    async def list_with_valuations(
        self,
        suburb: Optional[str] = None,
        suburb_id: Optional[int] = None,
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
        bbox: Optional[str] = None,
        sort_by: str = "underval_score",
        sort_dir: str = "desc",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        # Latest valuation subquery
        latest_val_subq = (
            select(
                MLValuation.property_id,
                func.max(MLValuation.predicted_at).label("max_predicted_at"),
            )
            .group_by(MLValuation.property_id)
            .subquery()
        )

        query = (
            select(Property, MLValuation)
            .outerjoin(
                latest_val_subq,
                latest_val_subq.c.property_id == Property.id,
            )
            .outerjoin(
                MLValuation,
                and_(
                    MLValuation.property_id == Property.id,
                    MLValuation.predicted_at == latest_val_subq.c.max_predicted_at,
                ),
            )
        )

        # Filters
        filters = []
        if status:
            filters.append(Property.status == status)
        if suburb:
            filters.append(Property.address_suburb.ilike(f"%{suburb}%"))
        if suburb_id:
            filters.append(Property.suburb_id == suburb_id)
        if postcode:
            filters.append(Property.address_postcode == postcode)
        if property_type:
            filters.append(Property.property_type == property_type)
        if bedrooms_min is not None:
            filters.append(Property.bedrooms >= bedrooms_min)
        if bedrooms_max is not None:
            filters.append(Property.bedrooms <= bedrooms_max)
        if price_min is not None:
            filters.append(Property.list_price >= price_min * 100)  # cents
        if price_max is not None:
            filters.append(Property.list_price <= price_max * 100)
        if land_size_min is not None:
            filters.append(Property.land_size_sqm >= land_size_min)
        if land_size_max is not None:
            filters.append(Property.land_size_sqm <= land_size_max)
        if underval_score_min is not None:
            filters.append(MLValuation.underval_score_pct >= underval_score_min)
        if bbox:
            try:
                sw_lat, sw_lng, ne_lat, ne_lng = map(float, bbox.split(","))
                filters.append(Property.latitude >= sw_lat)
                filters.append(Property.latitude <= ne_lat)
                filters.append(Property.longitude >= sw_lng)
                filters.append(Property.longitude <= ne_lng)
            except (ValueError, TypeError):
                pass

        if filters:
            query = query.where(and_(*filters))

        # Count
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        # Sort
        sort_col = {
            "underval_score": MLValuation.underval_score_pct,
            "price": Property.list_price,
            "listed_at": Property.listed_at,
            "suburb": Property.address_suburb,
        }.get(sort_by, MLValuation.underval_score_pct)

        order = desc(sort_col) if sort_dir == "desc" else sort_col
        query = query.order_by(order.nullslast()).limit(limit).offset(offset)

        rows = (await self.db.execute(query)).all()
        return [self._row_to_summary(p, v) for p, v in rows], total

    async def get_detail(self, property_id: int) -> dict:
        result = await self.db.execute(
            select(Property)
            .options(selectinload(Property.images), selectinload(Property.suburb))
            .where(Property.id == property_id)
        )
        prop = result.scalar_one_or_none()
        if not prop:
            raise HTTPException(status_code=404, detail="Property not found")
        val = await self.get_latest_valuation(property_id)
        return {**self._prop_to_dict(prop), "valuation": val, "images": [i.url for i in prop.images]}

    async def get_latest_valuation(self, property_id: int) -> Optional[dict]:
        result = await self.db.execute(
            select(MLValuation)
            .where(MLValuation.property_id == property_id)
            .order_by(desc(MLValuation.predicted_at))
            .limit(1)
        )
        val = result.scalar_one_or_none()
        if not val:
            return None
        return {
            "predicted_value": val.predicted_value_cents // 100 if val.predicted_value_cents else None,
            "underval_score_pct": val.underval_score_pct,
            "confidence_interval": [
                val.confidence_interval_low // 100 if val.confidence_interval_low else None,
                val.confidence_interval_high // 100 if val.confidence_interval_high else None,
            ],
            "feature_importances": val.feature_importances,
            "model_version": val.model_version,
            "predicted_at": val.predicted_at,
        }

    @staticmethod
    def _prop_to_dict(p: Property) -> dict:
        return {
            "id": p.id,
            "external_id": p.external_id,
            "source": p.source,
            "url": p.url,
            "status": p.status,
            "property_type": p.property_type,
            "address_street": p.address_street,
            "address_suburb": p.address_suburb,
            "address_postcode": p.address_postcode,
            "suburb_id": p.suburb_id,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "land_size_sqm": p.land_size_sqm,
            "floor_area_sqm": p.floor_area_sqm,
            "bedrooms": p.bedrooms,
            "bathrooms": p.bathrooms,
            "car_spaces": p.car_spaces,
            "year_built": p.year_built,
            "list_price": p.list_price // 100 if p.list_price else None,
            "price_guide_low": p.price_guide_low // 100 if p.price_guide_low else None,
            "price_guide_high": p.price_guide_high // 100 if p.price_guide_high else None,
            "listed_at": p.listed_at,
            "sold_at": p.sold_at,
            "sold_price": p.sold_price // 100 if p.sold_price else None,
            "description": p.description,
            "features": p.features,
            "agent_name": p.agent_name,
            "agency_name": p.agency_name,
            "first_seen_at": p.first_seen_at,
            "last_seen_at": p.last_seen_at,
        }

    @staticmethod
    def _row_to_summary(p: Property, v: Optional[MLValuation]) -> dict:
        return {
            "id": p.id,
            "source": p.source,
            "url": p.url,
            "status": p.status,
            "property_type": p.property_type,
            "address": f"{p.address_street}, {p.address_suburb} NSW {p.address_postcode}",
            "address_suburb": p.address_suburb,
            "address_postcode": p.address_postcode,
            "latitude": p.latitude,
            "longitude": p.longitude,
            "bedrooms": p.bedrooms,
            "bathrooms": p.bathrooms,
            "car_spaces": p.car_spaces,
            "land_size_sqm": p.land_size_sqm,
            "list_price": p.list_price // 100 if p.list_price else None,
            "listed_at": p.listed_at,
            "valuation": {
                "predicted_value": v.predicted_value_cents // 100 if v and v.predicted_value_cents else None,
                "underval_score_pct": v.underval_score_pct if v else None,
                "model_version": v.model_version if v else None,
            } if v else None,
        }
