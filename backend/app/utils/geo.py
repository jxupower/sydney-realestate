"""Geographic utility functions for the Sydney 150km radius constraint."""

import math
from typing import Optional

from app.config import settings

# Sydney CBD coordinates
SYDNEY_CBD_LAT = settings.sydney_cbd_lat  # -33.8688
SYDNEY_CBD_LNG = settings.sydney_cbd_lng  # 151.2093
SEARCH_RADIUS_KM = settings.search_radius_km  # 150.0

_EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return great-circle distance in km between two lat/lng points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def distance_to_cbd_km(lat: float, lng: float) -> float:
    """Return distance in km from a point to Sydney CBD."""
    return haversine_km(lat, lng, SYDNEY_CBD_LAT, SYDNEY_CBD_LNG)


def is_within_search_radius(lat: Optional[float], lng: Optional[float]) -> bool:
    """Return True if the point is within the 150km Sydney search radius."""
    if lat is None or lng is None:
        return False
    return distance_to_cbd_km(lat, lng) <= SEARCH_RADIUS_KM


def sydney_bbox() -> tuple[float, float, float, float]:
    """Return (sw_lat, sw_lng, ne_lat, ne_lng) bounding box for the 150km radius."""
    # 1 degree latitude ≈ 111 km; 1 degree longitude ≈ 111 * cos(lat) km
    lat_delta = SEARCH_RADIUS_KM / 111.0
    lng_delta = SEARCH_RADIUS_KM / (111.0 * math.cos(math.radians(SYDNEY_CBD_LAT)))
    return (
        SYDNEY_CBD_LAT - lat_delta,
        SYDNEY_CBD_LNG - lng_delta,
        SYDNEY_CBD_LAT + lat_delta,
        SYDNEY_CBD_LNG + lng_delta,
    )
