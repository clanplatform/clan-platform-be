"""
Custom middleware for request processing
"""
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from fastapi import FastAPI
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


def setup_middleware(app: FastAPI):
    """Setup all middleware for the application."""
    app.add_middleware(RequestContextMiddleware)

    # Dynamic CORS — origins loaded from the DB (tenants.allowed_origins for
    # tenant apps, usersetup_basic.allowed_origins for master users), cached
    # in Redis, with CORS_ORIGINS env var as a static fallback.
    from app.infrastructure.cors import DynamicCORSMiddleware
    from app.infrastructure.database.session import SessionLocal
    from app.infrastructure.redis_cache.redis_cache import redis_cache

    app.add_middleware(
        DynamicCORSMiddleware,
        session_factory=SessionLocal,
        redis_client=redis_cache.redis_client,
    )

    logger.info("Middleware configured successfully")
