"""SCC Market Intelligence Module — FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine, Base
from app.api import tenders, news, briefings, system, query, competitive_intel

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

# Create tables on startup (dev convenience — use Alembic migrations in production)
@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


# Register routers
app.include_router(tenders.router, prefix="/api")
app.include_router(news.router, prefix="/api")
app.include_router(briefings.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(competitive_intel.router, prefix="/api")


@app.get("/")
def root():
    return {"service": "SCC Market Intelligence API", "status": "running"}
