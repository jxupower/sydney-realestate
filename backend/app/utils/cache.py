"""Redis cache helpers using the synchronous redis client (Celery-compatible)."""

import json
from typing import Any, Optional

import redis as redis_sync

from app.config import settings

_client: Optional[redis_sync.Redis] = None


def get_redis() -> redis_sync.Redis:
    global _client
    if _client is None:
        _client = redis_sync.from_url(settings.redis_url, decode_responses=True)
    return _client


def cache_get(key: str) -> Optional[Any]:
    val = get_redis().get(key)
    if val is None:
        return None
    return json.loads(val)


def cache_set(key: str, value: Any, ttl_seconds: int = 3600) -> None:
    get_redis().setex(key, ttl_seconds, json.dumps(value, default=str))


def cache_delete(key: str) -> None:
    get_redis().delete(key)
