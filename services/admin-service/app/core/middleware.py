"""
Custom middleware for request processing
"""
import time
import uuid
import os
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to add request context and logging"""
    
    async def dispatch(self, request: Request, call_next):
        """
        Process each request, adding correlation ID and logging.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler in chain
            
        Returns:
            Response from the handler
        """
        # Generate or extract correlation ID
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        
        # Add correlation ID to request state
        request.state.correlation_id = correlation_id
        
        # Log request start
        start_time = time.time()
        logger.info(
            "Request started",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host if request.client else None
            }
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            
            # Log request completion
            logger.info(
                "Request completed",
                extra={
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration": f"{duration:.3f}s"
                }
            )
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration = time.time() - start_time
            
            # Log error
            logger.error(
                "Request failed",
                extra={
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "duration": f"{duration:.3f}s"
                },
                exc_info=True
            )
            raise


def _clan_cors_origins() -> list:
    """Allowed CORS origins from the CORS_ORIGINS env var (JSON list or CSV).

    Empty => no CORS (production default-deny); dev falls back to localhost.
    Authoritative CORS is the API gateway (Envoy); this only applies while
    admin-service is exposed directly (Render).
    """
    raw = (os.getenv("CORS_ORIGINS") or "").strip()
    if raw.startswith("["):
        try:
            return [str(o).strip() for o in json.loads(raw) if str(o).strip()]
        except Exception:
            return []
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    if not origins and os.getenv("ENVIRONMENT", "development").lower().startswith(("dev", "local")):
        origins = ["http://localhost:3000", "http://localhost:8080"]
    return origins


def setup_middleware(app: FastAPI):
    """
    Setup all middleware for the application.

    Args:
        app: FastAPI application instance
    """
    # Add request context middleware
    app.add_middleware(RequestContextMiddleware)

    # CORS (env-driven). Added last so it is the outermost layer and sets
    # headers on every response.
    origins = _clan_cors_origins()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials="*" not in origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    logger.info("Middleware configured successfully")
