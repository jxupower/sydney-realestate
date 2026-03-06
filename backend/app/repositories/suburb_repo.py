import json
from typing import Optional

from sqlalchemy import desc, select
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

    async def list_with_stats(
        self,
        lga: Optional[str] = None,
        postcode: Optional[str] = None,
        sort_by: str = "median_price",
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        query = select(Suburb)
        if lga:
            query = query.where(Suburb.lga.ilike(f"%{lga}%"))
        if postcode:
            query = query.where(Suburb.postcode == postcode)
        query = query.limit(limit).offset(offset)

        suburbs = (await self.db.execute(query)).scalars().all()

        result = []
        for s in suburbs:
            latest_stats = await self._get_latest_stats(s.id)
            result.append({
                "id": s.id,
                "name": s.name,
                "postcode": s.postcode,
                "lga": s.lga,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "stats": latest_stats,
            })

        # Sort in Python (simple for now; could push to DB)
        sort_map = {
            "median_price": lambda x: x["stats"].get("median_price") or 0,
            "capital_growth_3yr": lambda x: x["stats"].get("capital_growth_3yr") or 0,
            "rental_yield_pct": lambda x: x["stats"].get("rental_yield_pct") or 0,
        }
        result.sort(key=sort_map.get(sort_by, lambda x: 0), reverse=True)
        return result

    async def _get_latest_stats(self, suburb_id: int) -> dict:
        result = await self.db.execute(
            select(SuburbStats)
            .where(SuburbStats.suburb_id == suburb_id)
            .order_by(desc(SuburbStats.snapshot_date))
            .limit(1)
        )
        stats = result.scalar_one_or_none()
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
            "snapshot_date": stats.snapshot_date,
        }

    async def get_stats_history(self, suburb_id: int) -> list[dict]:
        result = await self.db.execute(
            select(SuburbStats)
            .where(SuburbStats.suburb_id == suburb_id)
            .order_by(SuburbStats.snapshot_date)
        )
        rows = result.scalars().all()
        return [
            {
                "snapshot_date": r.snapshot_date,
                "median_price": r.median_price,
                "rental_yield_pct": r.rental_yield_pct,
                "capital_growth_1yr": r.capital_growth_1yr,
                "capital_growth_3yr": r.capital_growth_3yr,
            }
            for r in rows
        ]

    async def get_geojson(self) -> dict:
        """Lightweight GeoJSON FeatureCollection for choropleth — suburbs with latest stats."""
        suburbs = (await self.db.execute(select(Suburb).where(Suburb.latitude.isnot(None)))).scalars().all()
        features = []
        for s in suburbs:
            stats = await self._get_latest_stats(s.id)
            # Use boundary_geojson polygon if available, else a point
            if s.boundary_geojson:
                geometry = json.loads(s.boundary_geojson)
            else:
                geometry = {"type": "Point", "coordinates": [s.longitude, s.latitude]}

            features.append({
                "type": "Feature",
                "geometry": geometry,
                "properties": {
                    "id": s.id,
                    "name": s.name,
                    "postcode": s.postcode,
                    "median_price": stats.get("median_price"),
                    "capital_growth_3yr": stats.get("capital_growth_3yr"),
                    "rental_yield_pct": stats.get("rental_yield_pct"),
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
