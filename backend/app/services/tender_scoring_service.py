"""
Tender match scoring service.
Uses LLM to score SCC-relevant tenders for strategic fit.
"""

import json
import time
import logging
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.services.llm_client import call_llm_json
from app.models import Tender, TenderProbe, TenderScore, AwardedTender

logger = logging.getLogger(__name__)

_COMPETITIVE_INTEL_PATH = Path(__file__).resolve().parents[2] / "data" / "competitive_intelligence.json"


def load_competitive_intelligence() -> dict | None:
    """Load competitive_intelligence.json. Returns None gracefully if unavailable."""
    try:
        with open(_COMPETITIVE_INTEL_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("competitive_intelligence.json not found — scoring without competitive context")
        return None
    except Exception as exc:
        logger.warning("Failed to load competitive_intelligence.json: %s", exc)
        return None


def _apply_competitive_adjustments(
    score: int,
    reasoning: str,
    entity: str,
    category: str,
    competitive_intel: dict | None,
) -> tuple[int, str]:
    """Apply entity/category boosts and penalties from competitive intelligence.

    Returns (adjusted_score, updated_reasoning).
    """
    if not competitive_intel:
        return score, reasoning

    guidance = competitive_intel.get("scoring_guidance", {})
    adjustments = []
    delta = 0

    entity_lower = (entity or "").lower()

    for up_entity in guidance.get("score_up_entities", []):
        if up_entity.lower() in entity_lower or entity_lower in up_entity.lower():
            delta += 10
            adjustments.append(f"+10 entity ({up_entity})")
            break

    for down_entity in guidance.get("score_down_entities", []):
        if down_entity.lower() in entity_lower or entity_lower in down_entity.lower():
            delta -= 15
            adjustments.append(f"-15 entity ({down_entity})")
            break

    category_lower = (category or "").lower()
    for up_cat in guidance.get("score_up_categories", []):
        if up_cat.lower() in category_lower or category_lower in up_cat.lower():
            delta += 5
            adjustments.append(f"+5 category ({up_cat})")
            break

    for down_cat in guidance.get("score_down_categories", []):
        if down_cat.lower() in category_lower or category_lower in down_cat.lower():
            delta -= 20
            adjustments.append(f"-20 category ({down_cat})")
            break

    if delta != 0:
        adjusted = max(0, min(100, score + delta))
        note = f"Competitive context applied ({', '.join(adjustments)})"
        reasoning = f"{reasoning} [{note}]"
        return adjusted, reasoning

    return score, reasoning


# ---------------------------------------------------------------------------
# Issuer relevance multiplier
# ---------------------------------------------------------------------------

_GOVERNMENT_KW = [
    "ministry", "authority", "municipality", "commission", "council",
    "royal", "government", "public", "national", "state", "municipal",
    "directorate", "department of", "secretariat",
]

_STRATEGIC_CLIENTS = [
    "pdo", "petroleum development oman",
    "oq", "oqep",
    "oxy", "occidental",
    "shell", "bp", "total", "eni",
    "sohar", "duqm", "sezad",
    "nama water", "haya water",
]

_PRIVATE_INDICATORS = ["saoc", "llc", "l.l.c", "est.", "establishment", "ltd", "limited", "co."]


def get_issuer_relevance_multiplier(issuing_entity: str) -> float:
    """Return a score multiplier based on issuer strategic relevance.

    1.0  — Government / public sector or strategic private (PDO, OQ, etc.)
    0.3  — Non-strategic private company (farms, retail, small businesses)
    """
    if not issuing_entity:
        return 1.0
    el = issuing_entity.lower()
    if any(kw in el for kw in _GOVERNMENT_KW):
        return 1.0
    if any(c in el for c in _STRATEGIC_CLIENTS):
        return 1.0
    if any(ind in el for ind in _PRIVATE_INDICATORS):
        return 0.3
    return 1.0


def _score_to_recommendation(score: int) -> str:
    if score >= 90:
        return "MUST_BID"
    if score >= 70:
        return "STRONG_FIT"
    if score >= 50:
        return "CONSIDER"
    if score >= 30:
        return "WATCH"
    return "SKIP"


SCORING_SYSTEM_PROMPT = (
    "You are a strategic advisor to Sarooj Construction Company (SCC), a major "
    "Omani civil infrastructure contractor. SCC's core capabilities are: roads, "
    "bridges, tunnels, marine works, dams, pipelines, and large-scale civil "
    "infrastructure. SCC holds Excellent and First grade classifications.\n\n"
    "You will receive a JSON array of tenders. For each tender, produce a JSON "
    "object with:\n"
    "- tender_number: the tender number (string)\n"
    "- score: integer 0-100 indicating strategic fit for SCC\n"
    "- recommendation: one of 'MUST_BID', 'STRONG_FIT', 'CONSIDER', 'WATCH', 'SKIP'\n"
    "- reasoning: 1-2 sentence explanation\n\n"
    "HARD CONSTRAINTS (override all other scoring):\n"
    "- If the tender grade is ONLY Second, Third, or Fourth (without Excellent or First), the MAXIMUM score is 35 regardless of category match. SCC holds Excellent and First grade — Second/Third-only tenders are below SCC's operating scale.\n"
    "- If the tender fee is below 30 OMR AND the grade is Second/Third, the MAXIMUM score is 20. These are minor maintenance jobs.\n"
    "- School renovations, painting works, guard room construction, furniture supply, and similar small-scale maintenance: MAXIMUM score 30 even if the category technically matches.\n\n"
    "SCORING CRITERIA:\n"
    "90-100 (MUST_BID): Core SCC work (roads, bridges, marine, dams, pipelines) "
    "at scale, few tracked competitors, strong win probability.\n"
    "70-89 (STRONG_FIT): Good match to SCC capabilities, reasonable competition "
    "level, worth serious pursuit.\n"
    "50-69 (CONSIDER): Partial capability match or high competition. Bid if "
    "pipeline is thin.\n"
    "30-49 (WATCH): Marginal fit. Monitor for re-tender or scope changes.\n"
    "0-29 (SKIP): Outside SCC core capabilities, too small, or overwhelming "
    "competition.\n\n"
    "FACTORS TO WEIGH:\n"
    "- Scope alignment with SCC core work categories\n"
    "- Number and strength of tracked competitors (fewer = better)\n"
    "- Whether SCC competitors like Galfar, Strabag, L&T are already bidding\n"
    "- Re-tender status (re-tenders may indicate difficult scope or budget issues)\n"
    "- Governorate and regional considerations\n"
    "- Grade requirements vs SCC qualifications\n\n"
    "Return a JSON object with key 'scores' containing an array of score objects.\n"
    "Example: {\"scores\": [{\"tender_number\": \"123\", \"score\": 85, "
    "\"recommendation\": \"STRONG_FIT\", \"reasoning\": \"Core road work...\"}]}"
)



def score_tenders(db: Session) -> dict:
    """Score SCC-relevant tenders using LLM."""
    # Load competitive intelligence context (graceful if missing)
    competitive_intel = load_competitive_intelligence()

    # Get tenders that haven't been scored in last 24h
    cutoff = datetime.utcnow() - timedelta(hours=24)
    already_scored = set(
        r[0] for r in db.query(TenderScore.tender_number)
        .filter(TenderScore.scored_at >= cutoff).all()
    )

    scc_tenders = db.query(Tender).filter(Tender.is_scc_relevant == True).all()
    to_score = [t for t in scc_tenders if t.tender_number not in already_scored]

    if not to_score:
        return {"status": "no_tenders_to_score", "scored": 0}

    # Load probe data for enrichment
    probes = {p.tender_number: p for p in db.query(TenderProbe).all()}

    # Build tender descriptions
    tender_descs = []
    for t in to_score:
        probe = probes.get(t.tender_number)
        desc = {
            "tender_number": t.tender_number,
            "title": t.tender_name_en or t.tender_name_ar or "",
            "entity": t.entity_en or t.entity_ar or "",
            "category": t.category_en or "",
            "grade": t.grade_en or "",
            "fee": t.fee,
            "closing_date": t.bid_closing_date.isoformat() if t.bid_closing_date else None,
            "is_retender": t.is_retender,
        }
        if probe:
            bidders = probe.bidders or []
            purchasers = probe.purchasers or []
            from app.services.competitive_intel_service import resolve_competitor
            tracked = []
            for b in bidders:
                c = resolve_competitor(b.get("company", ""))
                if c:
                    tracked.append({"name": c, "role": "BID", "value": b.get("quoted_value", "")})
            for p in purchasers:
                c = resolve_competitor(p.get("company", ""))
                if c and not any(x["name"] == c and x["role"] == "BID" for x in tracked):
                    tracked.append({"name": c, "role": "DOCS"})
            desc["num_bidders"] = len(bidders)
            desc["num_purchasers"] = len(purchasers)
            desc["tracked_competitors"] = tracked
            if probe.nit:
                desc["governorate"] = probe.nit.get("governorate", "")
                desc["scope"] = probe.nit.get("scope", "")
        tender_descs.append(desc)

    # Enrich with historical entity context
    _enrich_with_entity_history(db, tender_descs)

    # Entity lookup for post-LLM multiplier
    entity_by_tn = {d["tender_number"]: d.get("entity", "") for d in tender_descs}

    # Process in batches of 8
    batch_size = 8
    scored = 0
    for i in range(0, len(tender_descs), batch_size):
        batch = tender_descs[i:i + batch_size]
        user_content = json.dumps(batch, ensure_ascii=False)
        result = call_llm_json(SCORING_SYSTEM_PROMPT, user_content)

        if result:
            items = result if isinstance(result, list) else result.get("scores", result.get("tenders", [result]))
            for item in items:
                tn = item.get("tender_number", "")
                if not tn:
                    continue

                # Apply issuer relevance multiplier post-LLM
                raw_score = item.get("score", 0)
                entity = entity_by_tn.get(tn, "")
                multiplier = get_issuer_relevance_multiplier(entity)
                final_score = min(100, int(raw_score * multiplier))

                reasoning = item.get("reasoning", "")
                recommendation = item.get("recommendation", "")
                if multiplier < 1.0:
                    reasoning = f"{reasoning} (Score reduced from {raw_score}: private non-strategic issuer)"
                    recommendation = _score_to_recommendation(final_score)

                # Apply competitive intelligence adjustments (entity/category boosts & penalties)
                category = next(
                    (d.get("category", "") for d in tender_descs if d.get("tender_number") == tn), ""
                )
                final_score, reasoning = _apply_competitive_adjustments(
                    final_score, reasoning, entity, category, competitive_intel
                )
                final_score = max(0, min(100, final_score))
                recommendation = _score_to_recommendation(final_score)

                existing = db.query(TenderScore).filter_by(tender_number=tn).first()
                if existing:
                    existing.score = final_score
                    existing.recommendation = recommendation
                    existing.reasoning = reasoning
                    existing.scored_at = datetime.utcnow()
                else:
                    db.add(TenderScore(
                        tender_number=tn,
                        score=final_score,
                        recommendation=recommendation,
                        reasoning=reasoning,
                    ))
                scored += 1
            db.commit()

        if i + batch_size < len(tender_descs):
            time.sleep(0.5)  # Rate limit

    return {"status": "success", "scored": scored, "total_scc": len(scc_tenders)}


def _enrich_with_entity_history(db: Session, tender_descs: list):
    """Add historical pricing context per entity to tender descriptions."""
    from app.services.competitive_intel_service import resolve_competitor

    try:
        awarded = db.query(AwardedTender).filter(
            AwardedTender.is_construction == True,
            AwardedTender.entity != None,
            AwardedTender.winning_value != None,
        ).all()
    except Exception:
        return

    if not awarded:
        return

    # Build per-entity stats
    entity_stats = defaultdict(lambda: {
        "count": 0, "values": [], "lowest_wins": 0,
        "total_with_lowest": 0, "comp_wins": Counter(),
    })

    for t in awarded:
        es = entity_stats[t.entity]
        es["count"] += 1
        if t.winning_value > 0:
            es["values"].append(t.winning_value)
        if t.lowest_bid and t.lowest_bid > 0:
            es["total_with_lowest"] += 1
            if abs(t.winning_value - t.lowest_bid) < 1:
                es["lowest_wins"] += 1
        winner = resolve_competitor(t.winner_company) if t.winner_company else None
        if winner:
            es["comp_wins"][winner] += 1

    # Attach to each tender description
    for desc in tender_descs:
        entity_name = desc.get("entity", "")
        if not entity_name:
            continue

        # Find matching entity (partial match)
        es = entity_stats.get(entity_name)
        if not es:
            for key, val in entity_stats.items():
                if entity_name.lower() in key.lower() or key.lower() in entity_name.lower():
                    es = val
                    break

        if es and es["count"] >= 3:
            avg_val = round(sum(es["values"]) / len(es["values"]), 2) if es["values"] else 0
            lowest_pct = round((es["lowest_wins"] / es["total_with_lowest"]) * 100, 1) if es["total_with_lowest"] > 0 else None
            top_winners = [f"{c} ({n} wins)" for c, n in es["comp_wins"].most_common(3)]

            desc["historical_context"] = {
                "entity_total_construction_awards": es["count"],
                "avg_winning_bid": avg_val,
                "lowest_bidder_wins_pct": lowest_pct,
                "top_winners_here": top_winners,
            }
