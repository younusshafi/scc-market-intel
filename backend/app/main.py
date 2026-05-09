"""SCC Market Intelligence Module — FastAPI application."""

import os
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine, Base
from app.api import tenders, news, briefings, system, query, competitive_intel, geo, entity_intel, dashboard, awarded

logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="SCC Market Intelligence",
    version="1.0.0",
    # Disable public API docs in production
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# ── Token authentication middleware ──────────────────────────────────────────
# All /api/* routes require a Bearer token except /api/system/health.
# Token is set via API_SECRET_TOKEN env var. If unset, auth is skipped (dev).

@app.middleware("http")
async def token_auth(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/") and path not in ("/api/system/health", "/api/system/health/"):
        api_token = os.environ.get("API_SECRET_TOKEN", "")
        if api_token:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer ") or auth_header[7:] != api_token:
                return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    _run_column_migrations()


def _run_column_migrations():
    """Add columns that create_all won't add to already-existing tables."""
    _settings = get_settings()

    if _settings.database_url.startswith("sqlite"):
        return

    migrations = [
        (
            "news_articles", "is_jv_mention",
            "ALTER TABLE news_articles ADD COLUMN is_jv_mention BOOLEAN DEFAULT FALSE"
        ),
        (
            "news_articles", "jv_details",
            "ALTER TABLE news_articles ADD COLUMN jv_details JSON"
        ),
    ]

    with engine.connect() as conn:
        for table, column, ddl in migrations:
            exists = conn.execute(text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :table AND column_name = :column"
            ), {"table": table, "column": column}).fetchone()

            if not exists:
                logger.info(f"Migration: adding {table}.{column}")
                conn.execute(text(ddl))
                conn.commit()
            else:
                logger.debug(f"Column {table}.{column} already exists, skipping")


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(tenders.router, prefix="/api")
app.include_router(news.router, prefix="/api")
app.include_router(briefings.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(competitive_intel.router, prefix="/api")
app.include_router(geo.router, prefix="/api")
app.include_router(entity_intel.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(awarded.router, prefix="/api")


@app.get("/")
def root():
    return {"service": "SCC Market Intelligence API", "status": "running"}
