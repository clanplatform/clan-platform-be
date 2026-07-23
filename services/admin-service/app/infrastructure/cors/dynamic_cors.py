"""
Dynamic CORS middleware — validates request origins against the tenants table
(tenant applications) and usersetup_basic (master/platform users).

Origins are cached in Redis (SET, TTL 300 s) and fall back to an in-memory
set when Redis is unavailable.  The DB is only queried on a cache miss or
after the TTL expires, so hot paths are O(1) Redis SISMEMBER calls.

Usage (admin service):
    from app.infrastructure.cors import DynamicCORSMiddleware, invalidate_cors_cache
    from app.infrastructure.database.session import SessionLocal
    from app.infrastructure.redis_cache.redis_cache import redis_cache

    app.add_middleware(
        DynamicCORSMiddleware,
        session_factory=SessionLocal,
        redis_client=redis_cache.redis_client,
    )

    # After updating a tenant's (or master user's) allowed_origins:
    invalidate_cors_cache(redis_cache.redis_client)
"""

import asyncio
import json
import logging
import os
import time
from typing import Callable, Optional, Set

from sqlalchemy import text

logger = logging.getLogger(__name__)

_REDIS_KEY = "cors:allowed_origins"
_DEFAULT_TTL = 300  # seconds


def _static_origins() -> Set[str]:
    """Origins from the CORS_ORIGINS env var (always allowed — backward compat)."""
    raw = (os.getenv("CORS_ORIGINS") or "").strip()
    if not raw:
        return set()
    if raw == "*":
        return {"*"}
    if raw.startswith("["):
        try:
            return {str(o).strip() for o in json.loads(raw) if str(o).strip()}
        except Exception:
            return set()
    return {o.strip() for o in raw.split(",") if o.strip()}


class DynamicCORSMiddleware:
    """
    ASGI middleware that validates CORS origins against active tenant and
    master-user records.

    Allowed origins = CORS_ORIGINS env var
                    ∪ tenants.allowed_origins (DB)
                    ∪ usersetup_basic.allowed_origins WHERE tenant_id IS NULL (DB).
    The DB set is Redis-cached (TTL 300 s) with in-memory fallback.
    """

    def __init__(
        self,
        app,
        session_factory: Callable,
        redis_client=None,
        ttl: int = _DEFAULT_TTL,
    ):
        self.app = app
        self.session_factory = session_factory
        self.redis = redis_client
        self.ttl = ttl
        self._mem: Set[str] = set()
        self._mem_ts: float = 0.0
        self._lock = asyncio.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        origin = headers.get(b"origin", b"").decode()

        if not origin:
            await self.app(scope, receive, send)
            return

        allowed = await self._is_allowed(origin)

        if not allowed:
            # Unknown origin — forward without CORS headers; browser will block.
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        if method == "OPTIONS":
            # Respond to preflight directly — do not hit the app.
            await send({
                "type": "http.response.start",
                "status": 204,
                "headers": [
                    (b"access-control-allow-origin", origin.encode()),
                    (b"access-control-allow-methods", b"GET,POST,PUT,PATCH,DELETE,OPTIONS"),
                    (b"access-control-allow-headers", b"*"),
                    (b"access-control-allow-credentials", b"true"),
                    (b"access-control-max-age", b"600"),
                    (b"content-length", b"0"),
                    (b"vary", b"Origin"),
                ],
            })
            await send({"type": "http.response.body", "body": b""})
            return

        # Inject CORS headers into the real response.
        async def send_with_cors(message):
            if message["type"] == "http.response.start":
                hdrs = list(message.get("headers", []))
                hdrs += [
                    (b"access-control-allow-origin", origin.encode()),
                    (b"access-control-allow-credentials", b"true"),
                    (b"vary", b"Origin"),
                ]
                message = {**message, "headers": hdrs}
            await send(message)

        await self.app(scope, receive, send_with_cors)

    async def _is_allowed(self, origin: str) -> bool:
        static = _static_origins()
        if "*" in static or origin in static:
            return True

        # Redis SISMEMBER — O(1), no lock needed. Only trust Redis when the
        # key actually exists; a missing/expired key must fall through to a
        # DB refresh (which repopulates Redis) instead of denying everything.
        if self.redis:
            try:
                if self.redis.exists(_REDIS_KEY):
                    return bool(self.redis.sismember(_REDIS_KEY, origin))
            except Exception:
                pass  # fall through to in-memory

        # In-memory cache with TTL.
        now = time.monotonic()
        if now - self._mem_ts > self.ttl:
            async with self._lock:
                if now - self._mem_ts > self.ttl:  # recheck after acquiring lock
                    await self._refresh()

        return origin in self._mem

    async def _refresh(self) -> None:
        """Reload allowed origins from the DB and push to Redis."""
        try:
            origins = await asyncio.get_event_loop().run_in_executor(
                None, self._load_from_db
            )
            self._mem = origins
            self._mem_ts = time.monotonic()

            if self.redis and origins:
                try:
                    pipe = self.redis.pipeline()
                    pipe.delete(_REDIS_KEY)
                    pipe.sadd(_REDIS_KEY, *origins)
                    pipe.expire(_REDIS_KEY, self.ttl)
                    pipe.execute()
                except Exception as exc:
                    logger.warning("DynamicCORS: Redis update failed: %s", exc)

        except Exception as exc:
            logger.error("DynamicCORS: DB refresh failed: %s", exc)
            self._mem_ts = time.monotonic()  # avoid tight retry loop on repeated failures

    def _load_from_db(self) -> Set[str]:
        """
        Union of:
          - tenants.allowed_origins          → tenant application origins
          - usersetup_basic.allowed_origins  → master/platform user origins
                                               (rows with tenant_id IS NULL)
        Each query is guarded independently so a missing table/column
        (e.g. migration not yet applied) cannot wipe out the other set.
        """
        origins: Set[str] = set()
        queries = (
            ("tenant",
             "SELECT unnest(allowed_origins) AS origin "
             "FROM tenants "
             "WHERE is_active = TRUE "
             "  AND deleted_at IS NULL "
             "  AND allowed_origins IS NOT NULL"),
            ("master-user",
             "SELECT unnest(allowed_origins) AS origin "
             "FROM usersetup_basic "
             "WHERE tenant_id IS NULL "
             "  AND status = 'active' "
             "  AND allowed_origins IS NOT NULL"),
        )
        try:
            db = self.session_factory()
            try:
                for label, query in queries:
                    try:
                        rows = db.execute(text(query)).fetchall()
                        origins.update(r[0] for r in rows if r[0])
                    except Exception as exc:
                        logger.warning("DynamicCORS: %s origins query failed: %s", label, exc)
                        try:
                            db.rollback()
                        except Exception:
                            pass
            finally:
                db.close()
        except Exception as exc:
            logger.error("DynamicCORS: DB query failed: %s", exc)
        return origins


def invalidate_cors_cache(redis_client) -> None:
    """
    Evict the Redis CORS cache so the next request reloads from DB.
    Call this after creating or updating a tenant's or master user's
    allowed_origins.
    """
    if redis_client:
        try:
            redis_client.delete(_REDIS_KEY)
            logger.debug("DynamicCORS: cache invalidated")
        except Exception as exc:
            logger.warning("DynamicCORS: cache invalidation failed: %s", exc)
