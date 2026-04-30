"""System health and scrape status endpoints."""

import threading
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.models import ScrapeLog, NewsArticle
from app.scrapers.news_scraper import detect_jv_mentions, NEWS_KW, OMAN_CONTEXT_KW

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def health_check():
    return {"status": "ok", "service": "scc-market-intel"}


@router.get("/scrape-status")
def scrape_status(db: Session = Depends(get_db)):
    """Get the latest scrape status for each type."""
    types = ["tenders", "news", "briefing", "tender_probe"]
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


@router.post("/run-probe")
def trigger_tender_probe():
    """Trigger the deep tender probe in a background thread.

    The probe scrapes tender detail pages for bidder/purchaser/NIT data.
    This is a long-running operation (can take 10+ minutes).
    """
    from app.jobs.probe_tenders import run_probe_job

    def _run():
        try:
            run_probe_job()
        except Exception as e:
            logger.error(f"Background probe failed: {e}")

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return {"status": "started", "message": "Tender probe running in background. Check /api/system/scrape-status for progress."}


@router.get("/probe-status")
def probe_status(db: Session = Depends(get_db)):
    """Get the latest tender probe status."""
    latest = (
        db.query(ScrapeLog)
        .filter(ScrapeLog.scrape_type == "tender_probe")
        .order_by(desc(ScrapeLog.started_at))
        .first()
    )
    if not latest:
        return {"status": "never_run"}
    return {
        "status": latest.status,
        "started_at": latest.started_at.isoformat() if latest.started_at else None,
        "completed_at": latest.completed_at.isoformat() if latest.completed_at else None,
        "records_found": latest.records_found,
        "records_new": latest.records_new,
        "records_updated": latest.records_updated,
        "error": latest.error_message,
        "details": latest.details,
    }


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


@router.post("/backfill-relevance")
def backfill_relevance(db: Session = Depends(get_db)):
    """Re-score existing news articles with stricter Oman-context filter."""
    articles = db.query(NewsArticle).all()
    marked_irrelevant = 0
    for a in articles:
        text = ((a.title or "") + " " + (a.summary or "")).lower()
        has_topic = any(kw in text for kw in NEWS_KW)
        has_oman = any(kw in text for kw in OMAN_CONTEXT_KW)
        new_relevant = has_topic and has_oman
        if a.is_relevant and not new_relevant:
            a.is_relevant = False
            marked_irrelevant += 1
    db.commit()
    return {"total_scanned": len(articles), "marked_irrelevant": marked_irrelevant}
