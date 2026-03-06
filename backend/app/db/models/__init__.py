# Import all models here so Alembic can detect them
from app.db.models.base import Base
from app.db.models.suburb import Suburb, SuburbStats
from app.db.models.property import Property, PropertyImage
from app.db.models.valuer_general import ValuerGeneralRecord
from app.db.models.valuation import MLValuation
from app.db.models.watchlist import Watchlist
from app.db.models.ingestion_log import IngestionRun
from app.db.models.osm import OsmAmenities

__all__ = [
    "Base",
    "Suburb", "SuburbStats",
    "Property", "PropertyImage",
    "ValuerGeneralRecord",
    "MLValuation",
    "Watchlist",
    "IngestionRun",
    "OsmAmenities",
]
