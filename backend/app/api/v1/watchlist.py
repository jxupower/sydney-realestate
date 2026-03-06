from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_session_id
from app.repositories.watchlist_repo import WatchlistRepository
from app.schemas.watchlist import WatchlistAdd, WatchlistUpdate

router = APIRouter()


@router.get("")
async def get_watchlist(
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    if not session_id:
        return []
    repo = WatchlistRepository(db)
    return await repo.get_by_session(session_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    body: WatchlistAdd,
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    if not session_id:
        raise HTTPException(status_code=400, detail="X-Session-ID header required")
    repo = WatchlistRepository(db)
    return await repo.add(session_id, body.property_id, body.notes)


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(
    property_id: int,
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    repo = WatchlistRepository(db)
    await repo.remove(session_id, property_id)


@router.patch("/{property_id}")
async def update_watchlist_notes(
    property_id: int,
    body: WatchlistUpdate,
    session_id: str = Depends(get_session_id),
    db: AsyncSession = Depends(get_db),
):
    repo = WatchlistRepository(db)
    return await repo.update_notes(session_id, property_id, body.notes)
