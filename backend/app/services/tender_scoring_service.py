"""
Tender match scoring service.
Uses Groq LLM to score SCC-relevant tenders for strategic fit.
"""

import json
import time
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.services.llm_client import call_llm_json
from app.models import Tender, TenderProbe, TenderScore

logger = logging.getLogger(__name__)

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
                existing = db.query(TenderScore).filter_by(tender_number=tn).first()
                if existing:
                    existing.score = item.get("score", 0)
                    existing.recommendation = item.get("recommendation", "")
                    existing.reasoning = item.get("reasoning", "")
                    existing.scored_at = datetime.utcnow()
                else:
                    db.add(TenderScore(
                        tender_number=tn,
                        score=item.get("score", 0),
                        recommendation=item.get("recommendation", ""),
                        reasoning=item.get("reasoning", ""),
                    ))
                scored += 1
            db.commit()

        if i + batch_size < len(tender_descs):
            time.sleep(0.5)  # Rate limit

    return {"status": "success", "scored": scored, "total_scc": len(scc_tenders)}
