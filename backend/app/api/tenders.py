"""Tender API endpoints."""

from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.core.database import get_db
from app.models import Tender, TenderScore, TenderProbe

router = APIRouter(prefix="/tenders", tags=["tenders"])


@router.get("/")
def list_tenders(
    view: str | None = None,
    scc_only: bool = False,
    retenders_only: bool = False,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
    db: Session = Depends(get_db),
):
    """List tenders with filtering and pagination."""
    q = db.query(Tender)

    if view:
        q = q.filter(Tender.view == view)
    if scc_only:
        q = q.filter(Tender.is_scc_relevant == True)
    if retenders_only:
        q = q.filter(Tender.is_retender == True)
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            (Tender.tender_name_en.ilike(pattern))
            | (Tender.tender_name_ar.ilike(pattern))
            | (Tender.tender_number.ilike(pattern))
            | (Tender.entity_en.ilike(pattern))
            | (Tender.entity_ar.ilike(pattern))
        )

    total = q.count()
    tenders = (
        q.order_by(desc(Tender.bid_closing_date))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "tenders": [_serialize_tender(t) for t in tenders],
    }


@router.get("/stats")
def tender_stats(db: Session = Depends(get_db)):
    """Dashboard summary statistics."""
    total = db.query(Tender).count()
    scc_relevant = db.query(Tender).filter(Tender.is_scc_relevant == True).count()
    retenders = db.query(Tender).filter(Tender.is_retender == True).count()

    # By view
    by_view = dict(
        db.query(Tender.view, func.count(Tender.id))
        .group_by(Tender.view)
        .all()
    )

    # Category breakdown
    categories = (
        db.query(Tender.category_en, func.count(Tender.id))
        .filter(Tender.category_en != None, Tender.category_en != "")
        .group_by(Tender.category_en)
        .order_by(desc(func.count(Tender.id)))
        .limit(15)
        .all()
    )

    # Top entities for SCC-relevant tenders
    entities = (
        db.query(Tender.entity_en, func.count(Tender.id))
        .filter(Tender.is_scc_relevant == True)
        .filter(Tender.entity_en != None, Tender.entity_en != "")
        .group_by(Tender.entity_en)
        .order_by(desc(func.count(Tender.id)))
        .limit(10)
        .all()
    )

    return {
        "total": total,
        "scc_relevant": scc_relevant,
        "retenders": retenders,
        "scc_pct": round(scc_relevant / max(total, 1) * 100, 1),
        "by_view": by_view,
        "categories": [{"name": c[0], "count": c[1]} for c in categories],
        "top_entities": [{"name": e[0], "count": e[1]} for e in entities],
    }


@router.get("/trend")
def tender_trend(db: Session = Depends(get_db)):
    """Monthly tender volume trend."""
    from collections import defaultdict

    tenders = db.query(Tender).filter(Tender.bid_closing_date != None).all()

    by_month = defaultdict(lambda: {"total": 0, "scc": 0})
    for t in tenders:
        if t.bid_closing_date:
            key = t.bid_closing_date.strftime("%Y-%m")
            by_month[key]["total"] += 1
            if t.is_scc_relevant:
                by_month[key]["scc"] += 1

    # Sort and return last 6 months
    sorted_months = sorted(by_month.items())[-6:]
    return [
        {"month": month, "total": data["total"], "scc": data["scc"]}
        for month, data in sorted_months
    ]


@router.get("/scored")
def get_scored_tenders(
    min_score: int = Query(0, ge=0, le=100),
    recommendation: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
    db: Session = Depends(get_db),
):
    """Get tenders with AI match scores, sorted by score descending.
    Only shows tenders with closing dates in the future or last 30 days."""
    from datetime import timedelta
    cutoff_date = date.today() - timedelta(days=30)

    q = (
        db.query(Tender, TenderScore)
        .join(TenderScore, Tender.tender_number == TenderScore.tender_number)
        .filter(TenderScore.score >= min_score)
        .filter(
            (Tender.bid_closing_date >= cutoff_date) | (Tender.bid_closing_date == None)
        )
    )

    if recommendation:
        q = q.filter(TenderScore.recommendation == recommendation.upper())

    total = q.count()
    results = (
        q.order_by(desc(TenderScore.score))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    # Preload probe data for all tender numbers in this page
    tender_numbers = [t.tender_number for t, _ in results]
    probes = {
        p.tender_number: p
        for p in db.query(TenderProbe)
        .filter(TenderProbe.tender_number.in_(tender_numbers))
        .all()
    } if tender_numbers else {}

    for tender, score in results:
        item = _serialize_tender(tender)
        item["score"] = score.score
        item["recommendation"] = score.recommendation
        item["reasoning"] = score.reasoning
        item["scored_at"] = score.scored_at.isoformat() if score.scored_at else None
        probe = probes.get(tender.tender_number)
        if probe:
            item["num_bidders"] = len(probe.bidders or [])
            item["num_purchasers"] = len(probe.purchasers or [])
        items.append(item)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "tenders": items,
    }


@router.post("/score")
def trigger_scoring(db: Session = Depends(get_db)):
    """Trigger AI scoring of SCC-relevant tenders."""
    from app.services.tender_scoring_service import score_tenders
    result = score_tenders(db)
    return result


def _serialize_tender(t: Tender) -> dict:
    return {
        "id": t.id,
        "tender_number": t.tender_number,
        "tender_name_ar": t.tender_name_ar,
        "tender_name_en": t.tender_name_en,
        "entity_ar": t.entity_ar,
        "entity_en": t.entity_en,
        "category_ar": t.category_ar,
        "category_en": t.category_en,
        "grade_ar": t.grade_ar,
        "grade_en": t.grade_en,
        "tender_type_ar": t.tender_type_ar,
        "tender_type_en": t.tender_type_en,
        "bid_closing_date": t.bid_closing_date.isoformat() if t.bid_closing_date else None,
        "sales_end_date": t.sales_end_date.isoformat() if t.sales_end_date else None,
        "fee": t.fee,
        "bank_guarantee": t.bank_guarantee,
        "view": t.view,
        "is_retender": t.is_retender,
        "is_scc_relevant": t.is_scc_relevant,
        "is_subcontract": t.is_subcontract,
        "first_seen": t.first_seen.isoformat() if t.first_seen else None,
    }
