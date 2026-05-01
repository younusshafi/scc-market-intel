"""Entity intelligence service — strategic analysis of government entities."""
import json, logging, re
from datetime import datetime
from collections import defaultdict

import requests
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Tender, TenderProbe, EntityIntelligence
from app.services.competitive_intel_service import resolve_competitor

logger = logging.getLogger(__name__)

ENTITY_SYSTEM_PROMPT = """You are a strategic advisor to Sarooj Construction Company (SCC), a major Omani Tier-1 civil infrastructure contractor with Excellent and First grade classifications. SCC's core work: roads, bridges, tunnels, dams, marine works, pipelines, major earthworks.

Analyse each government entity's tendering behaviour and recommend SCC's engagement strategy.

For each entity, provide:
- strategic_value: "critical", "high", "medium", "low"
- insight: 2-3 sentences about this entity's tender patterns, scale, competition level, and what SCC should expect
- action: 1 sentence specific action for SCC

CRITICAL SCORING RULES:
- SCC is a TIER-1 contractor with Excellent/First grade. Entities that issue small maintenance/renovation tenders (Second/Third grade, fee < 50 OMR) are LOW value regardless of tender count.
- Entities that issue major infrastructure tenders (fee >= 200 OMR, Excellent grade, roads/bridges/ports/dams) are HIGH or CRITICAL.
- Ministry of Education issues mostly small school renovations — rate LOW unless they have major construction.
- Ministry of Housing and Urban Planning issues Sultan Haitham City mega-projects — rate HIGH or CRITICAL.
- MTCIT, OPAZ, SEZAD issue major roads/ports — rate HIGH.
- High tender COUNT does not mean high strategic value if the tenders are small-scale.

Reference actual numbers. No generic language.
Respond in JSON only. Return {"entities": [...]}"""


def _call_groq_json(system_prompt, user_content, retries=2):
    """Call Groq API expecting JSON response. Retries on failure with delay."""
    import time as _time
    settings = get_settings()
    if not settings.groq_api_key:
        logger.error("GROQ_API_KEY not set")
        return None
    headers = {"Authorization": f"Bearer {settings.groq_api_key}", "Content-Type": "application/json"}
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

    for attempt in range(retries):
        if attempt > 0:
            wait = 5 * attempt
            logger.info(f"Retrying in {wait}s (attempt {attempt + 1}/{retries})...")
            _time.sleep(wait)

        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=90)
        except requests.RequestException as e:
            logger.error(f"Groq API request exception: {e}")
            print(f"  ERROR: Groq request failed: {e}")
            continue

        if r.status_code == 429:
            error_msg = r.text[:500]
            logger.warning(f"Groq rate limited (429): {error_msg}")
            print(f"  RATE LIMITED: {error_msg[:200]}")
            continue
        elif r.status_code != 200:
            error_msg = r.text[:500]
            logger.error(f"Groq {r.status_code}: {error_msg}")
            print(f"  ERROR: Groq returned {r.status_code}: {error_msg[:200]}")
            return None

        text = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r'\[.*\]', text, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group())
                except:
                    pass
            logger.error(f"Failed to parse JSON: {text[:200]}")
            print(f"  ERROR: JSON parse failed: {text[:150]}")
            return None

    # All retries exhausted
    logger.error("All Groq retries exhausted")
    print("  ERROR: All retries exhausted")
    return None


def build_entity_intel(db: Session) -> dict:
    """Build AI-powered entity intelligence from tender and probe data."""
    tenders = db.query(Tender).all()
    probes = {p.tender_number: p for p in db.query(TenderProbe).all()}

    if not tenders:
        return {"status": "no_data", "built": 0}

    # Group tenders by entity
    entity_data = defaultdict(lambda: {
        "tenders": [], "scc_relevant": 0, "fees": [],
        "categories": [], "competitors": [],
    })

    for t in tenders:
        entity_name = t.entity_en or t.entity_ar or ""
        if not entity_name:
            continue

        entity_data[entity_name]["tenders"].append(t.tender_number)
        if t.is_scc_relevant:
            entity_data[entity_name]["scc_relevant"] += 1
        if t.fee:
            entity_data[entity_name]["fees"].append(t.fee)
        if t.category_en:
            entity_data[entity_name]["categories"].append(t.category_en)

        # Get competitor info from probes
        probe = probes.get(t.tender_number)
        if probe:
            for b in (probe.bidders or []):
                comp = resolve_competitor(b.get("company", ""))
                if comp and comp != "Sarooj":
                    entity_data[entity_name]["competitors"].append(comp)

    if not entity_data:
        return {"status": "no_entity_data", "built": 0}

    # Prioritize entities by SCC strategic relevance (not just count)
    # Score: SCC-relevant count * 10 + avg_fee_weight + competitor_presence
    def entity_score(item):
        name, data = item
        scc = data["scc_relevant"]
        avg_fee = (sum(data["fees"]) / len(data["fees"])) if data["fees"] else 0
        comp_count = len(set(data["competitors"]))
        return scc * 10 + min(avg_fee, 500) + comp_count * 5

    # Ensure critical entities are always included
    MUST_INCLUDE = [
        "Ministry of Housing and Urban Planning",
        "Ministry of Transport Communications and Information Technology",
        "Public Authority for Special Economic Zones and Free Zones",
        "Salalah Free Zone",
    ]
    must_include_entities = [(k, v) for k, v in entity_data.items()
                            if any(m.lower() in k.lower() for m in MUST_INCLUDE)]
    other_entities = [(k, v) for k, v in entity_data.items()
                     if not any(m.lower() in k.lower() for m in MUST_INCLUDE)]
    other_sorted = sorted(other_entities, key=entity_score, reverse=True)

    # Combine: must-include first, then top by score, capped at 15
    sorted_entities = must_include_entities + other_sorted
    sorted_entities = sorted_entities[:15]

    entity_summaries = []
    for entity_name, data in sorted_entities:
        cat_counts = defaultdict(int)
        for cat in data["categories"]:
            cat_counts[cat] += 1
        top_cats = sorted(cat_counts.items(), key=lambda x: -x[1])[:3]

        comp_counts = defaultdict(int)
        for comp in data["competitors"]:
            comp_counts[comp] += 1
        top_comps = sorted(comp_counts.items(), key=lambda x: -x[1])[:5]

        avg_fee = round(sum(data["fees"]) / len(data["fees"]), 2) if data["fees"] else 0

        summary = {
            "entity": entity_name,
            "total_tenders": len(data["tenders"]),
            "scc_relevant_count": data["scc_relevant"],
            "avg_fee": avg_fee,
            "top_categories": [c[0] for c in top_cats],
            "top_competitors": [{"name": c[0], "count": c[1]} for c in top_comps],
        }
        entity_summaries.append(summary)

    # Call LLM in batches of 5 to avoid context length issues
    import time as _time
    all_llm_entities = []
    batch_size = 5
    for i in range(0, len(entity_summaries), batch_size):
        batch = entity_summaries[i:i + batch_size]
        logger.info(f"Processing entity batch {i // batch_size + 1} ({len(batch)} entities)")
        print(f"  Processing batch {i // batch_size + 1}: {[b['entity'][:30] for b in batch]}")

        user_content = json.dumps(batch, ensure_ascii=False)
        result = _call_groq_json(ENTITY_SYSTEM_PROMPT, user_content)

        if result:
            entities_batch = result if isinstance(result, list) else result.get("entities", [])
            all_llm_entities.extend(entities_batch)
        else:
            logger.warning(f"Batch {i // batch_size + 1} failed")

        if i + batch_size < len(entity_summaries):
            _time.sleep(3)

    if not all_llm_entities:
        return {"status": "llm_failed", "built": 0}

    entities = all_llm_entities

    # Store in database
    built = 0
    for entity in entities:
        entity_name = entity.get("entity", "")
        if not entity_name:
            continue

        stats = next((s for s in entity_summaries if s["entity"] == entity_name), {})

        existing = db.query(EntityIntelligence).filter_by(entity_name=entity_name).first()
        if existing:
            existing.total_tenders = stats.get("total_tenders", 0)
            existing.scc_relevant_count = stats.get("scc_relevant_count", 0)
            existing.avg_fee = stats.get("avg_fee")
            existing.strategic_value = entity.get("strategic_value", "")
            existing.insight = entity.get("insight", "")
            existing.action = entity.get("action", "")
            existing.competitors_present = [c["name"] for c in stats.get("top_competitors", [])]
            existing.top_categories = stats.get("top_categories", [])
            existing.built_at = datetime.utcnow()
        else:
            db.add(EntityIntelligence(
                entity_name=entity_name,
                total_tenders=stats.get("total_tenders", 0),
                scc_relevant_count=stats.get("scc_relevant_count", 0),
                avg_fee=stats.get("avg_fee"),
                strategic_value=entity.get("strategic_value", ""),
                insight=entity.get("insight", ""),
                action=entity.get("action", ""),
                competitors_present=[c["name"] for c in stats.get("top_competitors", [])],
                top_categories=stats.get("top_categories", []),
            ))
        built += 1

    db.commit()
    return {"status": "success", "built": built}
