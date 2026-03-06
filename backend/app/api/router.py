from fastapi import APIRouter

from app.api.v1 import properties, suburbs, valuations, watchlist, admin

api_router = APIRouter()

api_router.include_router(properties.router, prefix="/properties", tags=["properties"])
api_router.include_router(suburbs.router, prefix="/suburbs", tags=["suburbs"])
api_router.include_router(valuations.router, prefix="/valuations", tags=["valuations"])
api_router.include_router(watchlist.router, prefix="/watchlist", tags=["watchlist"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
