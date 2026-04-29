"""System health and scrape status endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.models import ScrapeLog

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def health_check():
    return {"status": "ok", "service": "scc-market-intel"}


@router.get("/scrape-status")
def scrape_status(db: Session = Depends(get_db)):
    """Get the latest scrape status for each type."""
    types = ["tenders", "news", "briefing"]
    status = {}

    for scrape_type in types:
        latest = (
            db.query(ScrapeLog)
            .filter(ScrapeLog.scrape_type == scrape_type)
            .order_by(desc(ScrapeLog.started_at))
            .first()
        )
        if latest:
            status[scrape_type] = {
                "status": latest.status,
                "started_at": latest.started_at.isoformat() if latest.started_at else None,
                "completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
                "records_found": latest.records_found,
                "records_new": latest.records_new,
                "error": latest.error_message,
            }
        else:
            status[scrape_type] = {"status": "never_run"}

    return status
