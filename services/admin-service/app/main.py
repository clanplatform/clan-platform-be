"""
FastAPI Application Bootstrap
Main entry point for the Admin Service
"""
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import setup_middleware
from app.infrastructure.database.session import check_db_connection, create_tables
from app.infrastructure.redis_cache.redis_cache import redis_cache
from app.infrastructure.mongodb.mongodb_admin import mongodb_client
from app.api.v1.router import api_v1_router

# Setup logging
logger = setup_logging(log_level="INFO" if not settings.DEBUG else "DEBUG")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager - handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting Admin Service...")
    
    startup_errors = []
    
    # Initialize PostgreSQL connection
    try:
        logger.info("Initializing PostgreSQL connection...")
        if not check_db_connection():
            startup_errors.append("PostgreSQL connection failed")
            logger.error("PostgreSQL connection failed")
        else:
            # Create tables if they don't exist
            create_tables()
            logger.info("PostgreSQL connection established successfully")
    except Exception as e:
        startup_errors.append(f"PostgreSQL initialization error: {e}")
        logger.error(f"PostgreSQL initialization error: {e}", exc_info=True)
    
    # Initialize Redis connection
    try:
        logger.info("Initializing Redis connection...")
        if not redis_cache.is_available():
            logger.warning("Redis connection not available - continuing without cache")
        else:
            logger.info("Redis connection established successfully")
    except Exception as e:
        logger.warning(f"Redis initialization error: {e} - continuing without cache")
    
    # Initialize MongoDB connection (non-fatal — service runs without it)
    try:
        logger.info("Initializing MongoDB connection...")
        mongodb_client.connect()
        if mongodb_client.db is None:
            logger.warning("MongoDB connection failed - continuing without MongoDB")
        else:
            logger.info("MongoDB connection established successfully")
    except Exception as e:
        logger.warning(f"MongoDB initialization error: {e} - continuing without MongoDB")
    
    # Log critical connection failures but keep the service running so Render can bind the port.
    # Requests that require DB will return 503 until the database is reachable.
    if startup_errors:
        logger.error(f"Service started with {len(startup_errors)} degraded connection(s): {', '.join(startup_errors)}")
    else:
        logger.info("Admin Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Admin Service...")
    
    try:
        if redis_cache.redis_client:
            redis_cache.redis_client.close()
            logger.info("Redis connection closed")
    except Exception as e:
        logger.error(f"Error closing Redis connection: {e}")
    
    try:
        mongodb_client.close()
        logger.info("MongoDB connection closed")
    except Exception as e:
        logger.error(f"Error closing MongoDB connection: {e}")
    
    logger.info("Admin Service shutdown complete")


# Create FastAPI application
# In production, you may want to set docs_url=None and redoc_url=None for security
app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else "/docs",  # Keep docs enabled even in production for now
    redoc_url="/redoc" if settings.DEBUG else "/redoc",
    openapi_url="/openapi.json" if settings.DEBUG else "/openapi.json"
)

# Setup middleware
setup_middleware(app)

# Include API v1 router
app.include_router(api_v1_router)


@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint - shallow liveness check.
    Returns 200 if service is running, without querying dependencies.
    """
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION
        }
    )


@app.get("/health/cors", tags=["health"])
async def cors_debug():
    """
    CORS diagnostics — shows exactly which origins THIS deployment can see.
    - build_marker proves which code version is live
    - db origins are loaded live from this service's DATABASE_URL
    Remove or protect this endpoint once CORS is verified in production.
    """
    from app.infrastructure.cors.dynamic_cors import _static_origins
    from app.infrastructure.database.session import SessionLocal
    from sqlalchemy import text as _text

    result = {
        "build_marker": "cors-union-2026-07-11",
        "env_CORS_ORIGINS": sorted(_static_origins()),
        "tenant_origins": None,
        "master_user_origins": None,
        "db_error": None,
    }
    try:
        db = SessionLocal()
        try:
            rows = db.execute(_text(
                "SELECT unnest(allowed_origins) FROM tenants "
                "WHERE is_active = TRUE AND deleted_at IS NULL "
                "AND allowed_origins IS NOT NULL"
            )).fetchall()
            result["tenant_origins"] = sorted({r[0] for r in rows if r[0]})
        except Exception as exc:
            result["db_error"] = f"tenants query: {exc}"
            db.rollback()
        try:
            rows = db.execute(_text(
                "SELECT unnest(allowed_origins) FROM usersetup_basic "
                "WHERE tenant_id IS NULL AND status = 'active' "
                "AND allowed_origins IS NOT NULL"
            )).fetchall()
            result["master_user_origins"] = sorted({r[0] for r in rows if r[0]})
        except Exception as exc:
            result["db_error"] = (result["db_error"] or "") + f" | usersetup_basic query: {exc}"
            db.rollback()
        db.close()
    except Exception as exc:
        result["db_error"] = f"connection: {exc}"
    return result


@app.get("/", tags=["root"])
async def root():
    """Root endpoint"""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": settings.APP_DESCRIPTION,
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
