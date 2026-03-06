from typing import AsyncGenerator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_session_id(x_session_id: str = Header(default="")) -> str:
    """Browser UUID for session-based watchlist (no auth in MVP)."""
    return x_session_id


async def require_admin(x_admin_key: str = Header(default="")) -> None:
    """Protect admin endpoints with a static API key."""
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin key")
