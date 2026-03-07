import json
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.suburb import Suburb, SuburbStats
from app.repositories.base import BaseRepository


class SuburbRepository(BaseRepository[Suburb]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Suburb)

    async def get_by_name_postcode(self, name: str, postcode: str) -> Optional[Suburb]:
        result = await self.db.execute(
            select(Suburb).where(Suburb.name == name, Suburb.postcode == postcode)
        )
        return result.scalar_one_or_none()

    async def get_detail(self, suburb_id: int) -> dict:
        suburb = await self.get_by_id(suburb_id)
        if not suburb:
            raise HTTPException(status_code=404, detail="Suburb not found")
        stats = await self._get_latest_stats(suburb_id)
        history = await self.get_stats_history(suburb_id)
        return {
            "id": suburb.id,
            "name": suburb.name,
            "postcode": suburb.postcode,
            "lga": suburb.lga,
            "state": suburb.state,
            "latitude": suburb.latitude,
            "longitude": suburb.longitude,
            "stats": stats,
            "stats_history": history,
        }

    async def list_with_stats(
        self,
        lga: Optional[str] = None,
        postcode: Optional[str] = None,
        sort_by: str = "median_price",
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        # Latest stats per suburb — single JOIN to avoid N+1
        latest_date_sq = (
            select(
                SuburbStats.suburb_id,
                func.max(SuburbStats.snapshot_date).label("latest_date"),
            )
            .group_by(SuburbStats.suburb_id)
            .subquery()
        )

        # Map sort_by to column
        sort_col_map = {
            "median_price": SuburbStats.median_price,
            "capital_growth_3yr": SuburbStats.capital_growth_3yr,
            "rental_yield_pct": SuburbStats.rental_yield_pct,
        }
        sort_col = sort_col_map.get(sort_by, SuburbStats.median_price)

        base_stmt = (
            select(Suburb, SuburbStats)
            .outerjoin(latest_date_sq, latest_date_sq.c.suburb_id == Suburb.id)
            .outerjoin(
                SuburbStats,
                and_(
                    SuburbStats.suburb_id == Suburb.id,
                    SuburbStats.snapshot_date == latest_date_sq.c.latest_date,
                ),
            )
        )

        filters = []
        if lga:
            filters.append(Suburb.lga.ilike(f"%{lga}%"))
        if postcode:
            filters.append(Suburb.postcode == postcode)
        if filters:
            base_stmt = base_stmt.where(and_(*filters))

        # Total count
        count_sq = select(func.count()).select_from(base_stmt.subquery())
        total = (await self.db.execute(count_sq)).scalar_one()

        stmt = (
            base_stmt
            .order_by(desc(sort_col).nullslast())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self.db.execute(stmt)).all()

        items = [self._to_summary(s, stats) for s, stats in rows]
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    async def _get_latest_stats(self, suburb_id: int) -> dict:
        result = await self.db.execute(
            select(SuburbStats)
            .where(SuburbStats.suburb_id == suburb_id)
            .order_by(desc(SuburbStats.snapshot_date))
            .limit(1)
        )
        stats = result.scalar_one_or_none()
        return self._stats_to_dict(stats)

    async def get_stats_history(self, suburb_id: int) -> list[dict]:
        result = await self.db.execute(
            select(SuburbStats)
            .where(SuburbStats.suburb_id == suburb_id)
            .order_by(SuburbStats.snapshot_date)
        )
        return [self._stats_to_dict(r) for r in result.scalars().all()]

    async def get_geojson(self) -> dict:
        """GeoJSON FeatureCollection for choropleth — single query."""
        latest_date_sq = (
            select(
                SuburbStats.suburb_id,
                func.max(SuburbStats.snapshot_date).label("latest_date"),
            )
            .group_by(SuburbStats.suburb_id)
            .subquery()
        )
        stmt = (
            select(Suburb, SuburbStats)
            .where(Suburb.latitude.isnot(None))
            .outerjoin(latest_date_sq, latest_date_sq.c.suburb_id == Suburb.id)
            .outerjoin(
                SuburbStats,
                and_(
                    SuburbStats.suburb_id == Suburb.id,
                    SuburbStats.snapshot_date == latest_date_sq.c.latest_date,
                ),
            )
        )
        rows = (await self.db.execute(stmt)).all()

        features = []
        for suburb, stats in rows:
            geometry = (
                json.loads(suburb.boundary_geojson)
                if suburb.boundary_geojson
                else {"type": "Point", "coordinates": [suburb.longitude, suburb.latitude]}
            )
            features.append({
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "id": suburb.id,
                    "name": suburb.name,
                    "postcode": suburb.postcode,
                    "median_price": stats.median_price if stats else None,
                    "capital_growth_3yr": stats.capital_growth_3yr if stats else None,
                    "rental_yield_pct": stats.rental_yield_pct if stats else None,
                },
            })
        return {"type": "FeatureCollection", "features": features}

    async def upsert(self, name: str, postcode: str, **kwargs) -> tuple["Suburb", bool]:
        existing = await self.get_by_name_postcode(name, postcode)
        if existing:
            for k, v in kwargs.items():
                setattr(existing, k, v)
            await self.db.flush()
            return existing, False
        suburb = Suburb(name=name, postcode=postcode, **kwargs)
        self.db.add(suburb)
        await self.db.flush()
        await self.db.refresh(suburb)
        return suburb, True

    @staticmethod
    def _stats_to_dict(stats: Optional[SuburbStats]) -> dict:
        if not stats:
            return {}
        return {
            "median_price": stats.median_price,
            "rental_yield_pct": stats.rental_yield_pct,
            "capital_growth_1yr": stats.capital_growth_1yr,
            "capital_growth_3yr": stats.capital_growth_3yr,
            "capital_growth_5yr": stats.capital_growth_5yr,
            "capital_growth_10yr": stats.capital_growth_10yr,
            "days_on_market_median": stats.days_on_market_median,
            "clearance_rate_pct": stats.clearance_rate_pct,
            "snapshot_date": str(stats.snapshot_date) if stats.snapshot_date else None,
        }

    @staticmethod
    def _to_summary(suburb: Suburb, stats: Optional[SuburbStats]) -> dict:
        return {
            "id": suburb.id,
            "name": suburb.name,
            "postcode": suburb.postcode,
            "lga": suburb.lga,
            "latitude": suburb.latitude,
            "longitude": suburb.longitude,
            "stats": SuburbRepository._stats_to_dict(stats),
        }
