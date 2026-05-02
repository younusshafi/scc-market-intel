"""Awarded tenders API — historical award intelligence."""

import json
from collections import Counter, defaultdict
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import AwardedTender

router = APIRouter(prefix="/awarded", tags=["awarded"])

TRACKED_COMPETITORS = [
    "Galfar", "Strabag", "Al Tasnim", "Sarooj", "L&T",
    "Towell", "Hassan Allam", "Arab Contractors", "Ozkar",
]

TRACKED_KEYWORDS = {
    "galfar": "Galfar",
    "strabag": "Strabag",
    "al tasnim": "Al Tasnim",
    "tasnim": "Al Tasnim",
    "sarooj": "Sarooj",
    "larsen": "L&T",
    "l&t": "L&T",
    "towell": "Towell",
    "hassan allam": "Hassan Allam",
    "arab contractors": "Arab Contractors",
    "ozkar": "Ozkar",
}


def _resolve_winner(name: str) -> str | None:
    """Resolve a company name to a tracked competitor."""
    if not name:
        return None
    low = name.lower()
    for keyword, comp in TRACKED_KEYWORDS.items():
        if keyword in low:
            return comp
    return None


@router.get("/stats")
def get_awarded_stats(db: Session = Depends(get_db)):
    """Summary statistics for awarded tenders."""
    total = db.query(AwardedTender).count()
    construction = db.query(AwardedTender).filter(AwardedTender.is_construction == True).count()
    with_details = db.query(AwardedTender).filter(AwardedTender.winner_company != None).count()

    # Date range
    all_dates = [r[0] for r in db.query(AwardedTender.awarded_date).filter(
        AwardedTender.awarded_date != None, AwardedTender.awarded_date != ''
    ).all()]
    date_range = None
    if all_dates:
        date_range = {"from": min(all_dates)[:10], "to": max(all_dates)[:10]}

    # Total contract value (where available)
    from sqlalchemy import func
    total_value_row = db.query(func.sum(AwardedTender.winning_value)).filter(
        AwardedTender.winning_value != None
    ).scalar()

    # Top winners (from winner_company field)
    winner_counts = Counter()
    winner_values = defaultdict(float)
    winners_with_data = db.query(AwardedTender).filter(
        AwardedTender.winner_company != None
    ).all()
    for t in winners_with_data:
        resolved = _resolve_winner(t.winner_company)
        if resolved:
            winner_counts[resolved] += 1
            if t.winning_value:
                winner_values[resolved] += t.winning_value

    top_winners = [
        {"company": comp, "wins": count, "total_value": round(winner_values.get(comp, 0), 2)}
        for comp, count in winner_counts.most_common(10)
    ]

    # Top entities
    entity_counts = Counter()
    entity_construction = Counter()
    for r in db.query(AwardedTender.entity, AwardedTender.is_construction).all():
        if r[0]:
            entity_counts[r[0]] += 1
            if r[1]:
                entity_construction[r[0]] += 1

    top_entities = [
        {"entity": entity, "count": count, "construction": entity_construction.get(entity, 0)}
        for entity, count in entity_counts.most_common(10)
    ]

    return {
        "total_awarded": total,
        "construction_awarded": construction,
        "with_bid_details": with_details,
        "date_range": date_range,
        "total_contract_value": round(total_value_row, 2) if total_value_row else None,
        "top_winners": top_winners,
        "top_entities": top_entities,
    }


@router.get("/winners")
def get_awarded_winners(db: Session = Depends(get_db)):
    """Competitor win rate analysis from awarded data."""
    # Get all awarded tenders with bidder details
    with_bidders = db.query(AwardedTender).filter(
        AwardedTender.bidders_json != None
    ).all()

    # Also count wins from winner_company field
    all_awarded = db.query(AwardedTender).filter(
        AwardedTender.winner_company != None
    ).all()

    comp_wins = Counter()
    comp_bids = Counter()
    comp_values = defaultdict(float)
    comp_categories = defaultdict(set)
    comp_entities = defaultdict(Counter)

    # Count wins
    for t in all_awarded:
        resolved = _resolve_winner(t.winner_company)
        if resolved:
            comp_wins[resolved] += 1
            if t.winning_value:
                comp_values[resolved] += t.winning_value
            if t.category:
                comp_categories[resolved].add(t.category)
            if t.entity:
                comp_entities[resolved][t.entity] += 1

    # Count bids (from bidders_json)
    for t in with_bidders:
        try:
            bidders = json.loads(t.bidders_json) if t.bidders_json else []
        except (json.JSONDecodeError, TypeError):
            continue
        for b in bidders:
            company = b.get('company', '') if isinstance(b, dict) else ''
            resolved = _resolve_winner(company)
            if resolved:
                comp_bids[resolved] += 1

    # Build response
    competitors = []
    for comp in TRACKED_COMPETITORS:
        wins = comp_wins.get(comp, 0)
        bids = comp_bids.get(comp, 0)
        if wins == 0 and bids == 0:
            continue
        win_rate = round((wins / bids) * 100, 1) if bids > 0 else 0
        total_val = comp_values.get(comp, 0)
        avg_val = round(total_val / wins, 2) if wins > 0 else 0

        top_ents = [e for e, _ in comp_entities.get(comp, Counter()).most_common(3)]

        competitors.append({
            "company": comp,
            "total_wins": wins,
            "total_bids": bids,
            "win_rate": win_rate,
            "total_contract_value": round(total_val, 2),
            "avg_winning_bid": avg_val,
            "categories": list(comp_categories.get(comp, set()))[:5],
            "top_entities": top_ents,
        })

    competitors.sort(key=lambda x: x["total_wins"], reverse=True)
    return {"competitors": competitors}


@router.get("/entity-history")
def get_entity_history(entity: str = Query(...), db: Session = Depends(get_db)):
    """Per-entity award history."""
    # Partial match on entity name
    tenders = db.query(AwardedTender).filter(
        AwardedTender.entity.ilike(f"%{entity}%")
    ).all()

    if not tenders:
        return {"entity": entity, "total_awarded": 0}

    construction = [t for t in tenders if t.is_construction]
    with_bidders_count = [t for t in tenders if t.num_bidders and t.num_bidders > 0]
    avg_bidders = (sum(t.num_bidders for t in with_bidders_count) / len(with_bidders_count)) if with_bidders_count else None

    with_values = [t for t in tenders if t.winning_value and t.winning_value > 0]
    avg_value = (sum(t.winning_value for t in with_values) / len(with_values)) if with_values else None

    # Competitors present
    comp_set = set()
    for t in tenders:
        resolved = _resolve_winner(t.winner_company)
        if resolved:
            comp_set.add(resolved)

    # Recent awards
    sorted_tenders = sorted(tenders, key=lambda t: t.awarded_date or '', reverse=True)
    recent = [{
        "tender_number": t.tender_number,
        "title": t.tender_title,
        "awarded_date": t.awarded_date,
        "winner": t.winner_company,
        "value": t.winning_value,
    } for t in sorted_tenders[:10]]

    return {
        "entity": tenders[0].entity if tenders else entity,
        "total_awarded": len(tenders),
        "construction_awarded": len(construction),
        "avg_num_bidders": round(avg_bidders, 1) if avg_bidders else None,
        "avg_winning_value": round(avg_value, 2) if avg_value else None,
        "competitors_present": sorted(comp_set),
        "recent_awards": recent,
    }


@router.get("/price-benchmark")
def get_price_benchmark(category: str = Query("Construction"), db: Session = Depends(get_db)):
    """Price-to-win data for a category."""
    tenders = db.query(AwardedTender).filter(
        AwardedTender.category.ilike(f"%{category}%"),
        AwardedTender.winning_value != None,
        AwardedTender.winning_value > 0,
    ).all()

    if not tenders:
        return {
            "category": category,
            "sample_size": 0,
        }

    values = sorted(t.winning_value for t in tenders)
    median_idx = len(values) // 2
    median = values[median_idx] if values else 0

    spreads = [t.bid_spread_pct for t in tenders if t.bid_spread_pct is not None]
    avg_spread = (sum(spreads) / len(spreads)) if spreads else None

    # Lowest bidder wins %
    lowest_wins = sum(1 for t in tenders if t.lowest_bid and t.winning_value and
                      abs(t.winning_value - t.lowest_bid) < 1)
    lowest_pct = round((lowest_wins / len(tenders)) * 100, 1) if tenders else None

    return {
        "category": category,
        "sample_size": len(tenders),
        "avg_winning_value": round(sum(values) / len(values), 2),
        "median_winning_value": round(median, 2),
        "avg_bid_spread_pct": round(avg_spread, 1) if avg_spread else None,
        "lowest_wins_pct": lowest_pct,
    }


# === NEW ANALYTICS ENDPOINTS ===

@router.get("/analytics")
def get_award_analytics(db: Session = Depends(get_db)):
    """Return computed award analytics (from cache or compute fresh)."""
    from app.services.award_analytics_service import get_cached_analytics, compute_award_analytics

    cached = get_cached_analytics()
    if cached:
        return cached

    # Compute fresh
    result = compute_award_analytics(db)
    result["computed_at"] = None  # Will be set by the service
    return result


@router.get("/insights")
def get_award_insights():
    """Return AI-generated strategic insights."""
    from app.jobs.generate_award_insights import get_cached_insights

    cached = get_cached_insights()
    if cached:
        return cached
    return {"insights": [], "generated_at": None, "status": "not_computed"}


@router.post("/compute")
def compute_analytics(db: Session = Depends(get_db)):
    """Trigger analytics computation + AI insights generation."""
    from app.services.award_analytics_service import compute_award_analytics
    from app.jobs.generate_award_insights import generate_insights

    # Step 1: Compute analytics
    analytics = compute_award_analytics(db)
    if not analytics or analytics.get("status") == "no_data":
        return {"status": "no_data", "message": "No awarded tender data found"}

    # Step 2: Generate AI insights
    insights_result = generate_insights(db)

    return {
        "status": "success",
        "analytics_computed": True,
        "total_tenders_analysed": analytics.get("total_tenders_analysed", 0),
        "insights_generated": len(insights_result.get("insights", [])),
    }


@router.get("/competitor-history")
def get_competitor_history(company: str = Query(...), db: Session = Depends(get_db)):
    """Yearly performance history for a specific competitor."""
    from app.services.award_analytics_service import get_cached_analytics, compute_award_analytics

    cached = get_cached_analytics()
    if not cached:
        cached = compute_award_analytics(db)

    if not cached or cached.get("status") == "no_data":
        return {"company": company, "yearly": []}

    # Find in competitor_deep
    comp_deep = cached.get("competitor_deep", {})
    comp_data = comp_deep.get(company)

    if not comp_data:
        # Try fuzzy match
        for name, data in comp_deep.items():
            if company.lower() in name.lower():
                comp_data = data
                company = name
                break

    if not comp_data:
        return {"company": company, "yearly": [], "message": "Competitor not found"}

    # Extract yearly from yearly_trends
    yearly_trends = cached.get("yearly_trends", [])
    yearly = []
    for yt in yearly_trends:
        comp_stats = yt.get("competitors", {}).get(company, {})
        if comp_stats:
            yearly.append({
                "year": yt["year"],
                "bids": comp_stats.get("bids", 0),
                "wins": comp_stats.get("wins", 0),
                "win_rate": comp_stats.get("win_rate", 0),
                "value_won": comp_stats.get("value_won", 0),
            })

    return {
        "company": company,
        "summary": {
            "total_bids": comp_data.get("total_bids", 0),
            "wins": comp_data.get("wins", 0),
            "win_rate": comp_data.get("win_rate", 0),
            "total_value_won": comp_data.get("total_value_won", 0),
            "avg_winning_bid": comp_data.get("avg_winning_bid", 0),
            "trend": comp_data.get("trend", "stable"),
            "top_entities": comp_data.get("top_entities", []),
            "size_brackets": comp_data.get("size_brackets", {}),
        },
        "yearly": yearly,
    }


@router.get("/scc-performance")
def get_scc_performance(db: Session = Depends(get_db)):
    """SCC's full performance breakdown."""
    from app.services.award_analytics_service import get_cached_analytics, compute_award_analytics

    cached = get_cached_analytics()
    if not cached:
        cached = compute_award_analytics(db)

    if not cached or cached.get("status") == "no_data":
        return {"status": "no_data"}

    scc = cached.get("scc_performance", {})
    pricing = cached.get("pricing", {})

    return {
        **scc,
        "market_lowest_bidder_wins_pct": pricing.get("lowest_bidder_wins_pct"),
        "market_avg_spread_pct": pricing.get("avg_bid_spread_pct"),
    }
