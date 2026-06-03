"""
FastAPI Application Bootstrap
Main entry point for the Admin Service
"""
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import sys

from app.core.config import settings
from app.core.logging import setup_logging
from app.core.middleware import setup_middleware
from app.infrastructure.database.session import check_db_connection, create_tables
from app.infrastructure.cache.redis_cache import redis_cache
from app.infrastructure.mongodb.mongo_client import mongodb_client
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
        if not redis_cache.client:
            startup_errors.append("Redis connection failed")
            logger.error("Redis connection failed")
        else:
            logger.info("Redis connection established successfully")
    except Exception as e:
        startup_errors.append(f"Redis initialization error: {e}")
        logger.error(f"Redis initialization error: {e}", exc_info=True)
    
    # Initialize MongoDB connection
    try:
        logger.info("Initializing MongoDB connection...")
        mongodb_client.connect()
        if not mongodb_client.db:
            startup_errors.append("MongoDB connection failed")
            logger.error("MongoDB connection failed")
        else:
            logger.info("MongoDB connection established successfully")
    except Exception as e:
        startup_errors.append(f"MongoDB initialization error: {e}")
        logger.error(f"MongoDB initialization error: {e}", exc_info=True)
    
    # Check if any critical connections failed
    if startup_errors:
        logger.error(f"Startup failed with {len(startup_errors)} error(s): {', '.join(startup_errors)}")
        sys.exit(1)
    
    logger.info("Admin Service started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Admin Service...")
    
    try:
        redis_cache.close()
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
