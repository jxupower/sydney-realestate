from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import engine
from app.db.models.base import Base
from app.api.router import api_router
from app.utils.logger import configure_logging, init_sentry

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_sentry(dsn=settings.sentry_dsn)
    logger.info("Starting Sydney Real Estate API", radius_km=settings.search_radius_km)
    yield
    await engine.dispose()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Sydney Real Estate Investment API",
    version="0.1.0",
    description="Find undervalued Sydney properties using ML valuation",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
