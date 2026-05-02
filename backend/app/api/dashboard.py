"""Dashboard API endpoints — priority actions for Command Centre."""

from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Tender, TenderScore, TenderProbe, NewsIntelligence
from app.services.competitive_intel_service import resolve_competitor

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/priority-actions")
def get_priority_actions(db: Session = Depends(get_db)):
    """Return max 5 priority items for the Command Centre."""
    actions = []
    today = date.today()

    # --- 1. ACT NOW: Tenders closing within 7 days where SCC is active ---
    cutoff_7d = today + timedelta(days=7)
    closing_soon = (
        db.query(Tender)
        .filter(Tender.bid_closing_date != None)
        .filter(Tender.bid_closing_date >= today)
        .filter(Tender.bid_closing_date <= cutoff_7d)
        .filter(Tender.is_scc_relevant == True)
        .all()
    )

    probes_map = {}
    if closing_soon:
        tender_numbers = [t.tender_number for t in closing_soon]
        probes = db.query(TenderProbe).filter(TenderProbe.tender_number.in_(tender_numbers)).all()
        probes_map = {p.tender_number: p for p in probes}

    for t in closing_soon:
        probe = probes_map.get(t.tender_number)
        scc_active = False
        competitors = []
        scc_bid_value = None

        if probe:
            for b in (probe.bidders or []):
                comp = resolve_competitor(b.get("company", ""))
                if comp == "Sarooj":
                    scc_active = True
                    try:
                        scc_bid_value = float(b.get("quoted_value", 0) or 0)
                    except (ValueError, TypeError):
                        pass
                elif comp:
                    competitors.append(comp)
            for p in (probe.purchasers or []):
                comp = resolve_competitor(p.get("company", ""))
                if comp == "Sarooj":
                    scc_active = True
                elif comp and comp not in competitors:
                    competitors.append(comp)

        # Also check if score >= 85
        score_row = db.query(TenderScore).filter_by(tender_number=t.tender_number).first()
        high_scored = score_row and score_row.score >= 85

        if scc_active or high_scored:
            days_left = (t.bid_closing_date - today).days
            desc_parts = [t.tender_name_en or t.tender_number]
            desc_parts.append(f"closes in {days_left} day{'s' if days_left != 1 else ''}")
            if scc_bid_value and scc_bid_value > 0:
                if scc_bid_value >= 1_000_000:
                    desc_parts.append(f"SCC bid OMR {scc_bid_value/1_000_000:.2f}M")
                else:
                    desc_parts.append(f"SCC bid OMR {scc_bid_value:,.0f}")
            if competitors:
                desc_parts.append(f"{len(competitors)} competitors: {', '.join(competitors[:3])}")

            actions.append({
                "type": "act_now",
                "title": t.tender_name_en or t.tender_number,
                "description": " — ".join(desc_parts),
                "tender_number": t.tender_number,
                "urgency": days_left,
                "closing_date": t.bid_closing_date.isoformat(),
            })

    # --- 2. NEW ACTIVITY: Competitor purchases detected recently (from probe timestamps) ---
    # Look for probes with recent purchase dates in purchasers
    all_probes = db.query(TenderProbe).all()
    cutoff_str = (today - timedelta(days=7)).isoformat()

    for probe in all_probes:
        recent_comps = []
        for p in (probe.purchasers or []):
            purchase_date = p.get("purchase_date", "")
            if purchase_date and purchase_date >= cutoff_str:
                comp = resolve_competitor(p.get("company", ""))
                if comp and comp != "Sarooj":
                    recent_comps.append(comp)

        if recent_comps and len(actions) < 8:
            actions.append({
                "type": "new_activity",
                "title": probe.tender_name or probe.tender_number,
                "description": f"{', '.join(set(recent_comps))} purchased docs in last 7 days",
                "tender_number": probe.tender_number,
                "urgency": 50,
            })

    # --- 3. OPPORTUNITY: Tenders scored 90+ where SCC hasn't purchased docs ---
    high_scores = (
        db.query(TenderScore)
        .filter(TenderScore.score >= 90)
        .order_by(TenderScore.score.desc())
        .limit(10)
        .all()
    )

    for score in high_scores:
        probe = db.query(TenderProbe).filter_by(tender_number=score.tender_number).first()
        scc_has_docs = False
        if probe:
            for p in (probe.purchasers or []):
                if resolve_competitor(p.get("company", "")) == "Sarooj":
                    scc_has_docs = True
                    break
            for b in (probe.bidders or []):
                if resolve_competitor(b.get("company", "")) == "Sarooj":
                    scc_has_docs = True
                    break

        if not scc_has_docs:
            tender = db.query(Tender).filter_by(tender_number=score.tender_number).first()
            if tender:
                actions.append({
                    "type": "opportunity",
                    "title": tender.tender_name_en or tender.tender_number,
                    "description": f"Score {score.score} — {score.recommendation} — SCC not yet participating",
                    "tender_number": score.tender_number,
                    "urgency": 100 - score.score,
                })

    # Sort: act_now first (by urgency/days), then new_activity, then opportunity
    type_order = {"act_now": 0, "new_activity": 1, "opportunity": 2}
    actions.sort(key=lambda a: (type_order.get(a["type"], 3), a.get("urgency", 99)))

    return {"actions": actions[:5]}


@router.get("/metrics")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """Return meaningful dashboard metrics for Command Centre."""
    today = date.today()

    # Tracked projects: fee >= 200, construction category
    SCC_CAT_KW = ["construction", "ports", "roads", "bridges", "pipeline",
                  "electromechanical", "dams", "marine"]
    all_tenders = db.query(Tender).filter(Tender.is_scc_relevant == True).all()
    tracked_projects = sum(
        1 for t in all_tenders
        if (t.fee or 0) >= 200 and any(kw in (t.category_en or "").lower() for kw in SCC_CAT_KW)
    )

    # Competitive tenders: probes with tracked competitors
    probes = db.query(TenderProbe).all()
    competitive_count = 0
    scc_active_count = 0
    for probe in probes:
        has_competitor = False
        has_scc = False
        for b in (probe.bidders or []):
            comp = resolve_competitor(b.get("company", ""))
            if comp and comp != "Sarooj":
                has_competitor = True
            if comp == "Sarooj":
                has_scc = True
        for p in (probe.purchasers or []):
            comp = resolve_competitor(p.get("company", ""))
            if comp and comp != "Sarooj":
                has_competitor = True
            if comp == "Sarooj":
                has_scc = True
        if has_competitor:
            competitive_count += 1
        if has_scc:
            scc_active_count += 1

    # Closing this month
    month_end = today + timedelta(days=30)
    closing_this_month = (
        db.query(Tender)
        .filter(Tender.is_scc_relevant == True)
        .filter(Tender.bid_closing_date != None)
        .filter(Tender.bid_closing_date >= today)
        .filter(Tender.bid_closing_date <= month_end)
        .count()
    )

    # News signals: HIGH priority
    news_high = (
        db.query(NewsIntelligence)
        .filter(NewsIntelligence.priority == "HIGH")
        .filter(NewsIntelligence.relevant == True)
        .count()
    )

    return {
        "tracked_projects": tracked_projects,
        "competitive_tenders": competitive_count,
        "scc_active": scc_active_count,
        "closing_this_month": closing_this_month,
        "news_signals": news_high,
    }
