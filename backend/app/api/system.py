"""System health and scrape status endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.models import ScrapeLog, NewsArticle
from app.scrapers.news_scraper import detect_jv_mentions

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


@router.post("/backfill-jv")
def backfill_jv_mentions(db: Session = Depends(get_db)):
    """One-time backfill: scan existing news articles for JV mentions."""
    articles = db.query(NewsArticle).all()
    updated = 0
    for a in articles:
        jv_details = detect_jv_mentions(a.title or "", a.summary or "")
        is_jv = jv_details is not None
        if is_jv != a.is_jv_mention or (is_jv and jv_details != a.jv_details):
            a.is_jv_mention = is_jv
            a.jv_details = jv_details
            updated += 1
    db.commit()
    return {"total_scanned": len(articles), "updated": updated}
