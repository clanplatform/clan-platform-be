"""
Dynamic CORS middleware.

Allowed origins = settings.CORS_ORIGINS (static, from env)
              + clients.allowed_origins   (per-client, from DB, cached in Redis)

Redis cache key : cors:allowed_origins  (TTL 5 min)
Cache is invalidated automatically on next TTL expiry; for immediate effect
after adding/updating a client, restart the service or flush the key.
"""
import json
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import settings

logger = logging.getLogger(__name__)

_CACHE_KEY = "cors:allowed_origins"
_CACHE_TTL = 300  # seconds


class DynamicCORSMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, session_factory, redis_client=None):
        super().__init__(app)
        self.session_factory = session_factory
        self.redis_client = redis_client

    # ── origin resolution ────────────────────────────────────────────────────

    def _load_client_origins(self) -> list:
        """Return all allowed_origins from active clients (Redis-cached)."""
        if self.redis_client:
            try:
                cached = self.redis_client.get(_CACHE_KEY)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        origins: list = []
        try:
            db = self.session_factory()
            try:
                from app.clients.models.clients import Client
                rows = (
                    db.query(Client.allowed_origins)
                    .filter(
                        Client.is_active == True,
                        Client.deleted_at == None,
                        Client.allowed_origins != None,
                    )
                    .all()
                )
                for (row_origins,) in rows:
                    if row_origins:
                        origins.extend(row_origins)
            finally:
                db.close()
        except Exception as exc:
            logger.warning("[CORS] could not load client origins from DB: %s", exc)

        if self.redis_client:
            try:
                self.redis_client.setex(_CACHE_KEY, _CACHE_TTL, json.dumps(origins))
            except Exception:
                pass

        return origins

    def _is_allowed(self, origin: str) -> bool:
        if not origin:
            return True
        # Static origins (env var)
        if "*" in settings.CORS_ORIGINS or origin in settings.CORS_ORIGINS:
            return True
        # Per-client DB origins
        return origin in self._load_client_origins()

    # ── middleware dispatch ───────────────────────────────────────────────────

    async def dispatch(self, request: Request, call_next):
        origin = request.headers.get("origin", "")

        if request.method == "OPTIONS":
            if self._is_allowed(origin):
                return Response(status_code=204, headers=self._headers(origin))
            return Response(status_code=403)

        response = await call_next(request)

        if origin and self._is_allowed(origin):
            for key, val in self._headers(origin).items():
                response.headers[key] = val

        return response

    @staticmethod
    def _headers(origin: str) -> dict:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, PATCH, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization, Content-Type, X-Correlation-ID",
            "Access-Control-Max-Age": "600",
        }
