from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.valuation import MLValuation
from app.repositories.base import BaseRepository


class ValuationRepository(BaseRepository[MLValuation]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, MLValuation)

    async def get_active_model_info(self) -> dict:
        """Return the most recently used model version and its aggregate metrics."""
        result = await self.db.execute(
            select(MLValuation.model_version)
            .order_by(desc(MLValuation.predicted_at))
            .limit(1)
        )
        version = result.scalar_one_or_none()
        if not version:
            return {"model_version": None, "status": "no model trained yet"}
        return {"model_version": version, "status": "active"}

    async def get_latest_for_property(self, property_id: int) -> Optional[MLValuation]:
        """Return the most recent MLValuation for a property."""
        result = await self.db.execute(
            select(MLValuation)
            .where(MLValuation.property_id == property_id)
            .order_by(desc(MLValuation.predicted_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def bulk_insert(self, records: list[dict]) -> int:
        """Bulk-insert ML valuation records. Returns count inserted."""
        objects = [MLValuation(**r) for r in records]
        self.db.add_all(objects)
        await self.db.flush()
        return len(objects)
