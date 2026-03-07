"""Async Redis cache helpers using redis.asyncio.

All functions fail silently if Redis is unavailable — the API falls back
to hitting the database directly. This makes local dev and tests work
without requiring a running Redis instance.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)

_client: Optional[Any] = None   # redis.asyncio.Redis, lazily created


def _make_client():
    try:
        import redis.asyncio as aioredis
        from app.config import settings
        return aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
    except Exception as exc:
        logger.warning("Redis client creation failed", error=str(exc))
        return None


async def _get_client():
    global _client
    if _client is None:
        _client = _make_client()
    return _client


async def cache_get(key: str) -> Optional[Any]:
    r = await _get_client()
    if r is None:
        return None
    try:
        val = await r.get(key)
        return json.loads(val) if val is not None else None
    except Exception:
        return None


async def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    r = await _get_client()
    if r is None:
        return
    try:
        await r.setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception:
        pass


async def cache_delete(key: str) -> None:
    r = await _get_client()
    if r is None:
        return
    try:
        await r.delete(key)
    except Exception:
        pass


async def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching a glob pattern (e.g. 'suburbs:*')."""
    r = await _get_client()
    if r is None:
        return
    try:
        keys = await r.keys(pattern)
        if keys:
            await r.delete(*keys)
    except Exception:
        pass


def make_cache_key(*parts: Any) -> str:
    """Build a stable cache key from arbitrary parts."""
    raw = ":".join(str(p) for p in parts)
    if len(raw) > 200:
        return hashlib.md5(raw.encode()).hexdigest()
    return raw
