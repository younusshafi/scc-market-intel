"""News API endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.database import get_db
from app.models import NewsArticle, NewsIntelligence, NewsTenderLink

router = APIRouter(prefix="/news", tags=["news"])


@router.get("/")
def list_news(
    competitor_only: bool = False,
    source: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=10, le=100),
    db: Session = Depends(get_db),
):
    """List news articles with filtering."""
    q = db.query(NewsArticle).filter(NewsArticle.is_relevant == True)

    if competitor_only:
        q = q.filter(NewsArticle.is_competitor_mention == True)
    if source:
        q = q.filter(NewsArticle.source.ilike(f"%{source}%"))
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            (NewsArticle.title.ilike(pattern))
            | (NewsArticle.summary.ilike(pattern))
        )

    total = q.count()
    articles = (
        q.order_by(desc(NewsArticle.published))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "pages": (total + page_size - 1) // page_size,
        "articles": [_serialize_article(a) for a in articles],
    }


@router.get("/stats")
def news_stats(db: Session = Depends(get_db)):
    """News summary statistics."""
    total = db.query(NewsArticle).filter(NewsArticle.is_relevant == True).count()
    competitor_mentions = (
        db.query(NewsArticle)
        .filter(NewsArticle.is_competitor_mention == True)
        .count()
    )

    # By source
    by_source = (
        db.query(NewsArticle.source, func.count(NewsArticle.id))
        .filter(NewsArticle.is_relevant == True)
        .group_by(NewsArticle.source)
        .order_by(desc(func.count(NewsArticle.id)))
        .all()
    )

    return {
        "total": total,
        "competitor_mentions": competitor_mentions,
        "by_source": [{"source": s[0], "count": s[1]} for s in by_source],
    }


@router.get("/jv-mentions")
def jv_mentions(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=10, le=100),
    db: Session = Depends(get_db),
):
    """List news articles that mention joint ventures, consortiums, or partnerships."""
    q = db.query(NewsArticle).filter(NewsArticle.is_jv_mention == True)
    total = q.count()
    articles = (
        q.order_by(desc(NewsArticle.published))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "pages": (total + page_size - 1) // page_size,
        "articles": [_serialize_article(a) for a in articles],
    }


@router.get("/jv-stats")
def jv_stats(db: Session = Depends(get_db)):
    """JV mention summary statistics."""
    total_jv = db.query(NewsArticle).filter(NewsArticle.is_jv_mention == True).count()

    # Get all JV articles to count partner appearances
    jv_articles = (
        db.query(NewsArticle)
        .filter(NewsArticle.is_jv_mention == True)
        .all()
    )

    partner_counts = {}
    for a in jv_articles:
        if a.jv_details:
            for jv in a.jv_details:
                for partner in jv.get("partners", []):
                    partner_counts[partner] = partner_counts.get(partner, 0) + 1

    top_partners = sorted(partner_counts.items(), key=lambda x: -x[1])

    return {
        "total_jv_mentions": total_jv,
        "top_partners": [{"name": p[0], "count": p[1]} for p in top_partners],
    }


@router.get("/intelligence")
def get_news_intelligence(
    category: str | None = None,
    priority: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=10, le=100),
    db: Session = Depends(get_db),
):
    """Get news articles with AI intelligence analysis, sorted by priority."""
    priority_order = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}

    q = (
        db.query(NewsArticle, NewsIntelligence)
        .join(NewsIntelligence, NewsArticle.id == NewsIntelligence.article_id)
        .filter(NewsIntelligence.relevant == True)
    )

    if category:
        q = q.filter(NewsIntelligence.category == category.upper())
    if priority:
        q = q.filter(NewsIntelligence.priority == priority.upper())

    total = q.count()
    # Sort by priority (HIGH first), then by published date
    results = (
        q.order_by(NewsIntelligence.priority, desc(NewsArticle.published))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for article, intel in results:
        item = _serialize_article(article)
        item["scc_implication"] = intel.scc_implication
        item["intel_category"] = intel.category
        item["priority"] = intel.priority
        item["analysed_at"] = intel.analysed_at.isoformat() if intel.analysed_at else None
        items.append(item)

    return {
        "total": total,
        "page": page,
        "pages": (total + page_size - 1) // page_size,
        "articles": items,
    }


@router.post("/analyse")
def trigger_analysis(db: Session = Depends(get_db)):
    """Trigger AI analysis of recent news articles."""
    from app.services.news_intelligence_service import analyse_news
    result = analyse_news(db)
    return result


@router.get("/tender-links")
def get_news_tender_links(db: Session = Depends(get_db)):
    """Get all news-to-tender links."""
    links = db.query(NewsTenderLink).order_by(desc(NewsTenderLink.linked_at)).all()
    return {
        "links": [
            {
                "id": l.id,
                "article_id": l.article_id,
                "tender_number": l.tender_number,
                "match_confidence": l.match_confidence,
                "connection": l.connection,
                "scc_action": l.scc_action,
                "linked_at": l.linked_at.isoformat() if l.linked_at else None,
            }
            for l in links
        ]
    }


@router.post("/link-to-tenders")
def trigger_link_news_to_tenders(db: Session = Depends(get_db)):
    """Trigger AI news-to-tender linking."""
    from app.services.news_tender_linker_service import link_news_to_tenders
    return link_news_to_tenders(db)


def _serialize_article(a: NewsArticle) -> dict:
    return {
        "id": a.id,
        "source": a.source,
        "title": a.title,
        "link": a.link,
        "published": a.published.isoformat() if a.published else None,
        "summary": a.summary,
        "is_competitor_mention": a.is_competitor_mention,
        "mentioned_competitors": a.mentioned_competitors,
        "is_jv_mention": getattr(a, "is_jv_mention", False),
        "jv_details": getattr(a, "jv_details", None),
    }
