"""
Bounded natural language query service.
Supports 10-15 tested query patterns against the tender and news database.
"""

import re
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func, desc, or_

from app.models import Tender, NewsArticle
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Pattern definitions: regex -> handler function name
PATTERNS = [
    # Tender queries
    (r"(?:how many|total|count)\s+(?:active\s+)?tenders?", "count_tenders"),
    (r"(?:how many|count)\s+(?:scc|relevant|addressable)\s+tenders?", "count_scc_tenders"),
    (r"(?:show|list|find)\s+(?:scc|relevant)\s+(?:tenders?|opportunities)", "list_scc_tenders"),
    (r"(?:show|list|find)\s+re-?tenders?", "list_retenders"),
    (r"tenders?\s+(?:closing|due|deadline)\s+(?:this|next)\s+week", "closing_this_week"),
    (r"tenders?\s+(?:from|by|issued by)\s+(.+)", "tenders_by_entity"),
    (r"(?:show|list|find)\s+sub-?contract\s+tenders?", "list_subcontracts"),
    (r"(?:new|latest|recent)\s+tenders?\s+(?:today|this week)", "new_tenders"),
    # News queries
    (r"(?:any|show|latest)\s+(?:news|articles?)\s+(?:about|on|for)\s+(.+)", "news_about"),
    (r"competitor\s+(?:news|mentions?|activity)", "competitor_news"),
    (r"(?:news|articles?)\s+(?:from|this)\s+(?:today|this week|last week)", "recent_news"),
    # Stats queries
    (r"(?:market|category)\s+(?:breakdown|composition|mix)", "category_breakdown"),
    (r"(?:which|top|biggest)\s+(?:entities?|ministries?|agencies?)", "top_entities"),
    (r"(?:pipeline|overview|dashboard|summary|status)", "pipeline_summary"),
    (r"(?:when|last)\s+(?:was\s+)?(?:data|scrape)\s+(?:updated|refreshed|run)", "last_update"),
]


def process_query(db: Session, query: str) -> dict:
    """Match a natural language query to a handler and return results."""
    q = query.strip().lower()

    for pattern, handler_name in PATTERNS:
        match = re.search(pattern, q, re.IGNORECASE)
        if match:
            handler = globals().get(handler_name)
            if handler:
                try:
                    return handler(db, match)
                except Exception as e:
                    logger.error(f"Query handler {handler_name} failed: {e}")
                    return {"type": "error", "message": f"Error processing query: {str(e)}"}

    return {
        "type": "no_match",
        "message": "I can answer questions like: 'How many SCC tenders?', 'Show re-tenders', "
                   "'Tenders closing this week', 'News about Galfar', 'Market breakdown', "
                   "'Pipeline summary', 'Competitor news'.",
    }


# --- Tender handlers ---

def count_tenders(db: Session, match) -> dict:
    total = db.query(Tender).count()
    by_view = dict(
        db.query(Tender.view, func.count(Tender.id))
        .group_by(Tender.view).all()
    )
    return {
        "type": "stat",
        "message": f"There are {total} active tenders in the pipeline.",
        "data": {"total": total, "by_view": by_view},
    }


def count_scc_tenders(db: Session, match) -> dict:
    total = db.query(Tender).count()
    scc = db.query(Tender).filter(Tender.is_scc_relevant == True).count()
    pct = round(scc / max(total, 1) * 100, 1)
    return {
        "type": "stat",
        "message": f"{scc} tenders match SCC's categories and grades ({pct}% of {total} total).",
        "data": {"scc_relevant": scc, "total": total, "percentage": pct},
    }


def list_scc_tenders(db: Session, match) -> dict:
    tenders = (
        db.query(Tender)
        .filter(Tender.is_scc_relevant == True)
        .order_by(desc(Tender.bid_closing_date))
        .limit(20)
        .all()
    )
    return {
        "type": "list",
        "message": f"Found {len(tenders)} SCC-relevant tenders.",
        "data": [_tender_summary(t) for t in tenders],
    }


def list_retenders(db: Session, match) -> dict:
    tenders = (
        db.query(Tender)
        .filter(Tender.is_retender == True)
        .order_by(desc(Tender.bid_closing_date))
        .limit(20)
        .all()
    )
    return {
        "type": "list",
        "message": f"Found {len(tenders)} re-tenders in the current dataset.",
        "data": [_tender_summary(t) for t in tenders],
    }


def closing_this_week(db: Session, match) -> dict:
    today = datetime.utcnow().date()
    end_of_week = today + timedelta(days=(6 - today.weekday()) + 7)  # next Sunday
    tenders = (
        db.query(Tender)
        .filter(Tender.bid_closing_date >= today)
        .filter(Tender.bid_closing_date <= end_of_week)
        .order_by(Tender.bid_closing_date)
        .all()
    )
    return {
        "type": "list",
        "message": f"{len(tenders)} tenders closing between now and {end_of_week}.",
        "data": [_tender_summary(t) for t in tenders],
    }


def tenders_by_entity(db: Session, match) -> dict:
    entity = match.group(1).strip()
    pattern = f"%{entity}%"
    tenders = (
        db.query(Tender)
        .filter(
            or_(
                Tender.entity_en.ilike(pattern),
                Tender.entity_ar.ilike(pattern),
            )
        )
        .order_by(desc(Tender.bid_closing_date))
        .limit(20)
        .all()
    )
    return {
        "type": "list",
        "message": f"Found {len(tenders)} tenders from entities matching '{entity}'.",
        "data": [_tender_summary(t) for t in tenders],
    }


def list_subcontracts(db: Session, match) -> dict:
    tenders = (
        db.query(Tender)
        .filter(Tender.is_subcontract == True)
        .order_by(desc(Tender.bid_closing_date))
        .limit(20)
        .all()
    )
    return {
        "type": "list",
        "message": f"Found {len(tenders)} sub-contract tenders.",
        "data": [_tender_summary(t) for t in tenders],
    }


def new_tenders(db: Session, match) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=7)
    tenders = (
        db.query(Tender)
        .filter(Tender.first_seen >= cutoff)
        .order_by(desc(Tender.first_seen))
        .limit(20)
        .all()
    )
    return {
        "type": "list",
        "message": f"{len(tenders)} tenders first seen in the last 7 days.",
        "data": [_tender_summary(t) for t in tenders],
    }


# --- News handlers ---

def news_about(db: Session, match) -> dict:
    topic = match.group(1).strip()
    pattern = f"%{topic}%"
    articles = (
        db.query(NewsArticle)
        .filter(
            or_(
                NewsArticle.title.ilike(pattern),
                NewsArticle.summary.ilike(pattern),
            )
        )
        .order_by(desc(NewsArticle.published))
        .limit(15)
        .all()
    )
    return {
        "type": "list",
        "message": f"Found {len(articles)} news articles about '{topic}'.",
        "data": [_article_summary(a) for a in articles],
    }


def competitor_news(db: Session, match) -> dict:
    articles = (
        db.query(NewsArticle)
        .filter(NewsArticle.is_competitor_mention == True)
        .order_by(desc(NewsArticle.published))
        .limit(20)
        .all()
    )
    return {
        "type": "list",
        "message": f"{len(articles)} news articles mentioning tracked competitors.",
        "data": [_article_summary(a) for a in articles],
    }


def recent_news(db: Session, match) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=7)
    articles = (
        db.query(NewsArticle)
        .filter(NewsArticle.is_relevant == True)
        .filter(NewsArticle.published >= cutoff)
        .order_by(desc(NewsArticle.published))
        .limit(20)
        .all()
    )
    return {
        "type": "list",
        "message": f"{len(articles)} relevant news articles from the past week.",
        "data": [_article_summary(a) for a in articles],
    }


# --- Stats handlers ---

def category_breakdown(db: Session, match) -> dict:
    total = db.query(Tender).count()
    cats = (
        db.query(Tender.category_en, func.count(Tender.id))
        .filter(Tender.category_en != None, Tender.category_en != "")
        .group_by(Tender.category_en)
        .order_by(desc(func.count(Tender.id)))
        .limit(15)
        .all()
    )
    return {
        "type": "breakdown",
        "message": f"Market composition across {total} tenders:",
        "data": [
            {"category": c[0], "count": c[1], "pct": round(c[1] / max(total, 1) * 100, 1)}
            for c in cats
        ],
    }


def top_entities(db: Session, match) -> dict:
    entities = (
        db.query(Tender.entity_en, func.count(Tender.id))
        .filter(Tender.entity_en != None, Tender.entity_en != "")
        .group_by(Tender.entity_en)
        .order_by(desc(func.count(Tender.id)))
        .limit(10)
        .all()
    )
    return {
        "type": "breakdown",
        "message": "Top issuing entities:",
        "data": [{"entity": e[0], "count": e[1]} for e in entities],
    }


def pipeline_summary(db: Session, match) -> dict:
    total = db.query(Tender).count()
    scc = db.query(Tender).filter(Tender.is_scc_relevant == True).count()
    retenders = db.query(Tender).filter(Tender.is_retender == True).count()
    news_total = db.query(NewsArticle).filter(NewsArticle.is_relevant == True).count()
    comp_mentions = db.query(NewsArticle).filter(NewsArticle.is_competitor_mention == True).count()

    return {
        "type": "summary",
        "message": (
            f"Pipeline: {total} active tenders, {scc} SCC-relevant ({round(scc / max(total, 1) * 100, 1)}%), "
            f"{retenders} re-tenders. News: {news_total} articles, {comp_mentions} competitor mentions."
        ),
        "data": {
            "total_tenders": total,
            "scc_relevant": scc,
            "retenders": retenders,
            "news_total": news_total,
            "competitor_mentions": comp_mentions,
        },
    }


def last_update(db: Session, match) -> dict:
    from app.models import ScrapeLog
    latest = (
        db.query(ScrapeLog)
        .filter(ScrapeLog.status == "success")
        .order_by(desc(ScrapeLog.completed_at))
        .first()
    )
    if latest:
        return {
            "type": "stat",
            "message": f"Last successful scrape: {latest.scrape_type} at {latest.completed_at.strftime('%d %b %Y %H:%M UTC')}.",
            "data": {
                "type": latest.scrape_type,
                "completed_at": latest.completed_at.isoformat(),
                "records": latest.records_found,
            },
        }
    return {
        "type": "stat",
        "message": "No scrapes have run yet.",
        "data": None,
    }


# --- Helpers ---

def _tender_summary(t: Tender) -> dict:
    return {
        "tender_number": t.tender_number,
        "name": t.tender_name_en or t.tender_name_ar or "—",
        "entity": t.entity_en or t.entity_ar or "—",
        "category": t.category_en or t.category_ar or "—",
        "grade": t.grade_en or t.grade_ar or "—",
        "bid_closing": t.bid_closing_date.isoformat() if t.bid_closing_date else None,
        "is_retender": t.is_retender,
    }


def _article_summary(a: NewsArticle) -> dict:
    return {
        "title": a.title,
        "source": a.source,
        "published": a.published.isoformat() if a.published else None,
        "link": a.link,
        "competitors": a.mentioned_competitors,
    }
