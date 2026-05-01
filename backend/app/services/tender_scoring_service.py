"""
Tender match scoring service.
Uses Groq LLM to score SCC-relevant tenders for strategic fit.
"""

import json
import re
import time
import logging
from datetime import datetime, timedelta

import requests
from sqlalchemy.orm import Session

from app.core.config import get_settings
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


def _call_groq_json(system_prompt: str, user_content: str) -> dict | list | None:
    """Call Groq API expecting JSON response."""
    settings = get_settings()
    if not settings.groq_api_key:
        logger.error("GROQ_API_KEY not set")
        return None

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.3,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
    }

    logger.info("Calling Groq API for JSON scoring...")
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=90,
        )
    except requests.RequestException as e:
        logger.error(f"Groq API request failed: {e}")
        return None

    if r.status_code != 200:
        logger.error(f"Groq API returned {r.status_code}: {r.text[:300]}")
        return None

    text = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON array from response
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        logger.error(f"Failed to parse JSON from Groq: {text[:200]}")
        return None


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
        result = _call_groq_json(SCORING_SYSTEM_PROMPT, user_content)

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
            time.sleep(2)  # Rate limit

    return {"status": "success", "scored": scored, "total_scc": len(scc_tenders)}
