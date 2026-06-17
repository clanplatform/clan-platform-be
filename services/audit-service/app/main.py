from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import sys

from app.core.config import settings
from app.infrastructure.database.session import check_db_connection, create_tables
from app.api.v1.router import api_v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[audit-service] Starting up...")

    if not check_db_connection():
        print("[audit-service] ERROR: Cannot connect to database")
        sys.exit(1)

    create_tables()
    print("[audit-service] Database ready.")

    yield

    print("[audit-service] Shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_v1_router)


@app.get("/health", tags=["health"])
def health():
    return JSONResponse({"status": "healthy", "service": settings.APP_NAME, "version": settings.APP_VERSION})


@app.get("/", tags=["root"])
def root():
    return {"service": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
