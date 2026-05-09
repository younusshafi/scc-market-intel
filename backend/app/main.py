"""SCC Market Intelligence Module — FastAPI application."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import engine, Base
from app.api import tenders, news, briefings, system, query, competitive_intel, geo, entity_intel, dashboard, awarded

logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="SCC Market Intelligence",
    description="Tender and market intelligence API for Sarooj Construction Company",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create tables and run migrations on startup
@app.on_event("startup")
def startup():
    # Create any new tables (e.g. tender_probes)
    Base.metadata.create_all(bind=engine)

    # Add missing columns to existing tables (idempotent)
    _run_column_migrations()


def _run_column_migrations():
    """Add columns that create_all won't add to already-existing tables."""
    from app.core.config import get_settings
    _settings = get_settings()

    # SQLite: create_all handles everything since we start fresh
    if _settings.database_url.startswith("sqlite"):
        return

    # PostgreSQL: add missing columns to existing tables
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


# Register routers
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
