"""Generate AI strategic insights from award analytics data."""

import json
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.core.database import SessionLocal
from app.services.award_analytics_service import compute_award_analytics, _analytics_cache
from app.services.llm_client import call_llm_json

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

INSIGHTS_SYSTEM_PROMPT = """You are a competitive intelligence analyst with deep expertise in government construction procurement in Oman. You have been given comprehensive analytics from awarded construction tenders spanning 2012-2026 on the Oman Tender Board.

Produce exactly 5 strategic insights. Each insight must:
1. State a specific, non-obvious pattern found in the data
2. Quantify it with exact numbers and percentages
3. Explain what it means strategically for Sarooj Construction Company
4. Recommend a specific action

Categories of insights to cover (one each):
- PRICING: How should SCC price to win? What's the sweet spot?
- COMPETITION: Which competitor is the biggest threat and why?
- OPPORTUNITY: Where is SCC underperforming relative to capability?
- ENTITY: Which entity should SCC prioritize and why?
- TREND: What's changing in the market that SCC should adapt to?

RULES:
- Every number must come from the data provided. Do not invent statistics.
- Name specific competitors, entities, and tender categories.
- "SCC wins 8% of bids" is a fact. "SCC should bid more aggressively" is generic. Combine both: "SCC wins 8% of bids, but wins 18% when they're the lowest bidder. Price 5-10% below the median to improve win rate."
- Maximum 400 words total across all 5 insights.

Respond in JSON:
{"insights": [
  {
    "category": "PRICING",
    "title": "short title",
    "insight": "the full insight text",
    "action": "specific recommended action"
  },
  ...
]}"""

# Cache for insights
_insights_cache = {"data": None, "generated_at": None}


def get_cached_insights() -> dict | None:
    """Return cached insights if available."""
    if _insights_cache["data"]:
        return {"insights": _insights_cache["data"], "generated_at": _insights_cache["generated_at"]}
    return None


def generate_insights(db=None) -> dict:
    """Generate AI insights from computed analytics."""
    from datetime import datetime

    # Get or compute analytics
    if db is None:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False

    try:
        analytics = _analytics_cache.get("data")
        if not analytics:
            analytics = compute_award_analytics(db)

        if not analytics or analytics.get("status") == "no_data":
            return {"status": "no_analytics_data", "insights": []}

        # Build a summary for the LLM (don't send raw data, too large)
        summary = _build_analytics_summary(analytics)
        user_content = json.dumps(summary, ensure_ascii=False)

        logger.info(f"Sending {len(user_content)} chars to LLM for insights...")
        result = call_llm_json(INSIGHTS_SYSTEM_PROMPT, user_content, max_tokens=2048)

        if not result:
            return {"status": "llm_failed", "insights": []}

        insights = result if isinstance(result, list) else result.get("insights", [])

        # Cache
        _insights_cache["data"] = insights
        _insights_cache["generated_at"] = datetime.utcnow().isoformat()

        logger.info(f"Generated {len(insights)} insights")
        return {"status": "success", "insights": insights, "generated_at": _insights_cache["generated_at"]}

    finally:
        if close_db:
            db.close()


def _build_analytics_summary(analytics: dict) -> dict:
    """Build a concise summary for the LLM context."""
    summary = {
        "total_construction_tenders": analytics.get("total_tenders_analysed", 0),
        "total_with_bid_data": analytics.get("total_with_bidders", 0),
    }

    # SCC performance
    scc = analytics.get("scc_performance", {})
    summary["scc_performance"] = {
        "total_bids": scc.get("total_bids", 0),
        "wins": scc.get("total_wins", 0),
        "win_rate": scc.get("win_rate", 0),
        "total_value_won": scc.get("total_value_won", 0),
        "avg_winning_bid": scc.get("avg_winning_bid", 0),
        "avg_bid_position": scc.get("avg_bid_position"),
        "avg_gap_to_winner_pct": scc.get("avg_gap_to_winner_pct"),
        "lowest_bidder_win_rate": scc.get("lowest_bidder_win_rate"),
        "lost_to": scc.get("lost_to", [])[:5],
        "win_entities": scc.get("win_entities", [])[:5],
        "yearly_trend": scc.get("yearly", [])[-5:],  # Last 5 years
    }

    # Competitor summary (top 6 by bids)
    comp_deep = analytics.get("competitor_deep", {})
    comp_summary = []
    for comp, data in sorted(comp_deep.items(), key=lambda x: -x[1].get("total_bids", 0))[:6]:
        comp_summary.append({
            "name": comp,
            "bids": data.get("total_bids", 0),
            "wins": data.get("wins", 0),
            "win_rate": data.get("win_rate", 0),
            "total_value_won": data.get("total_value_won", 0),
            "avg_winning_bid": data.get("avg_winning_bid", 0),
            "trend": data.get("trend", "stable"),
            "top_entities": data.get("top_entities", [])[:3],
        })
    summary["competitors"] = comp_summary

    # Entity behaviour (top 8)
    entity_beh = analytics.get("entity_behaviour", [])[:8]
    summary["top_entities"] = [{
        "entity": e["entity"],
        "total_awards": e["total_awards"],
        "avg_contract_value": e.get("avg_contract_value", 0),
        "lowest_bidder_wins_pct": e.get("lowest_bidder_wins_pct"),
        "avg_bidders": e.get("avg_bidders"),
        "top_winners": e.get("top_winners", [])[:3],
    } for e in entity_beh]

    # Pricing
    pricing = analytics.get("pricing", {})
    summary["pricing"] = {
        "lowest_bidder_wins_pct": pricing.get("lowest_bidder_wins_pct"),
        "avg_bid_spread_pct": pricing.get("avg_bid_spread_pct"),
        "by_category": pricing.get("by_category", [])[:5],
    }

    # Yearly trends (last 5 years)
    yearly = analytics.get("yearly_trends", [])[-5:]
    summary["yearly_market"] = [{
        "year": y["year"],
        "total_awards": y["total_awards"],
        "total_value": y["total_value"],
        "avg_winning_bid": y["avg_winning_bid"],
        "avg_bidders": y["avg_bidders"],
    } for y in yearly]

    return summary


if __name__ == "__main__":
    result = generate_insights()
    print(f"\nResult: {result.get('status')}")
    for i, insight in enumerate(result.get("insights", []), 1):
        print(f"\n{i}. [{insight.get('category')}] {insight.get('title')}")
        print(f"   {insight.get('insight')}")
        print(f"   ACTION: {insight.get('action')}")
