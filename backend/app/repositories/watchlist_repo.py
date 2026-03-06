from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.watchlist import Watchlist
from app.repositories.base import BaseRepository


class WatchlistRepository(BaseRepository[Watchlist]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Watchlist)

    async def get_by_session(self, session_id: str) -> list[dict]:
        result = await self.db.execute(
            select(Watchlist)
            .options(selectinload(Watchlist.property))
            .where(Watchlist.session_id == session_id)
            .order_by(Watchlist.created_at.desc())
        )
        items = result.scalars().all()
        return [
            {
                "id": item.id,
                "property_id": item.property_id,
                "notes": item.notes,
                "created_at": item.created_at,
                "property": {
                    "address_street": item.property.address_street,
                    "address_suburb": item.property.address_suburb,
                    "list_price": item.property.list_price // 100 if item.property.list_price else None,
                    "status": item.property.status,
                    "url": item.property.url,
                } if item.property else None,
            }
            for item in items
        ]

    async def add(self, session_id: str, property_id: int, notes: Optional[str] = None) -> dict:
        item = Watchlist(session_id=session_id, property_id=property_id, notes=notes)
        self.db.add(item)
        await self.db.flush()
        await self.db.refresh(item)
        await self.db.commit()
        return {"id": item.id, "property_id": item.property_id, "notes": item.notes}

    async def remove(self, session_id: str, property_id: int) -> None:
        result = await self.db.execute(
            select(Watchlist).where(
                Watchlist.session_id == session_id,
                Watchlist.property_id == property_id,
            )
        )
        item = result.scalar_one_or_none()
        if item:
            await self.db.delete(item)
            await self.db.commit()

    async def update_notes(self, session_id: str, property_id: int, notes: str) -> dict:
        result = await self.db.execute(
            select(Watchlist).where(
                Watchlist.session_id == session_id,
                Watchlist.property_id == property_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise HTTPException(status_code=404, detail="Watchlist item not found")
        item.notes = notes
        await self.db.commit()
        return {"id": item.id, "property_id": item.property_id, "notes": item.notes}
