"""Entity intelligence service — strategic analysis of government entities."""
import json, logging, time
from datetime import datetime
from collections import defaultdict, Counter

from sqlalchemy.orm import Session

from app.services.llm_client import call_llm_json
from app.models import Tender, TenderProbe, EntityIntelligence, AwardedTender
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

CRITICAL RATING RULES:
- An entity is CRITICAL if it issues tenders with fee >= 200 OMR in SCC's core categories (roads, bridges, tunnels, dams, marine, pipelines) with Excellent/First grade, OR if SCC is already actively participating in their tenders, OR if multiple tracked competitors are active on their tenders.
- Average fee does NOT determine rating — one major project makes an entity strategically important regardless of their smaller tenders.
- Ministry of Housing and Urban Planning issues Sultan Haitham City — this alone makes them CRITICAL.
- An entity is LOW only if ALL their SCC-relevant tenders are small-scale (fee < 50 OMR, Second/Third grade, school renovations, minor maintenance).
- Do not rate an entity LOW if it has even one major infrastructure tender in SCC's core categories.

Reference actual numbers. No generic language.
Respond in JSON only. Return {"entities": [...]}"""



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

        # Get top 3 largest tenders by fee for this entity
        entity_tenders = [t for t in tenders if (t.entity_en or t.entity_ar or "") == entity_name]
        top_tenders = sorted([t for t in entity_tenders if t.fee], key=lambda t: -(t.fee or 0))[:3]
        max_fee = top_tenders[0].fee if top_tenders else 0

        # Check SCC and competitor presence
        scc_active = any(
            probe.tender_number in [t.tender_number for t in entity_tenders]
            and any(resolve_competitor(b.get("company","")) == "Sarooj" for b in (probe.bidders or []) + (probe.purchasers or []))
            for probe in probes.values()
            if probe.tender_number in [t.tender_number for t in entity_tenders]
        )

        summary = {
            "entity": entity_name,
            "total_tenders": len(data["tenders"]),
            "scc_relevant_count": data["scc_relevant"],
            "avg_fee": avg_fee,
            "max_fee": max_fee,
            "top_tenders": [{"name": (t.tender_name_en or "")[:60], "fee": t.fee, "category": t.category_en or ""} for t in top_tenders],
            "scc_active": scc_active,
            "top_categories": [c[0] for c in top_cats],
            "top_competitors": [{"name": c[0], "count": c[1]} for c in top_comps],
        }
        entity_summaries.append(summary)

    # Enrich with historical award data
    _enrich_entities_with_award_history(db, entity_summaries)

    # Call LLM in batches of 5 to avoid context length issues
    all_llm_entities = []
    batch_size = 5
    for i in range(0, len(entity_summaries), batch_size):
        batch = entity_summaries[i:i + batch_size]
        logger.info(f"Processing entity batch {i // batch_size + 1} ({len(batch)} entities)")
        print(f"  Processing batch {i // batch_size + 1}: {[b['entity'][:30] for b in batch]}")

        user_content = json.dumps(batch, ensure_ascii=False)
        result = call_llm_json(ENTITY_SYSTEM_PROMPT, user_content)

        if result:
            entities_batch = result if isinstance(result, list) else result.get("entities", [])
            all_llm_entities.extend(entities_batch)
        else:
            logger.warning(f"Batch {i // batch_size + 1} failed")

        if i + batch_size < len(entity_summaries):
            time.sleep(0.5)

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


def _enrich_entities_with_award_history(db: Session, entity_summaries: list):
    """Add historical award stats per entity for richer LLM context."""
    try:
        awarded = db.query(AwardedTender).filter(
            AwardedTender.is_construction == True,
            AwardedTender.entity != None,
        ).all()
    except Exception:
        return

    if not awarded:
        return

    # Build per-entity stats
    entity_stats = defaultdict(lambda: {
        "total_awarded": 0, "total_value": 0, "lowest_wins": 0,
        "total_with_lowest": 0, "comp_wins": Counter(),
    })

    for t in awarded:
        es = entity_stats[t.entity]
        es["total_awarded"] += 1
        if t.winning_value and t.winning_value > 0:
            es["total_value"] += t.winning_value
        if t.lowest_bid and t.winning_value and t.lowest_bid > 0:
            es["total_with_lowest"] += 1
            if abs(t.winning_value - t.lowest_bid) < 1:
                es["lowest_wins"] += 1
        winner = resolve_competitor(t.winner_company) if t.winner_company else None
        if winner:
            es["comp_wins"][winner] += 1

    # Attach to summaries
    for summary in entity_summaries:
        entity_name = summary.get("entity", "")
        # Try exact match first, then partial
        es = entity_stats.get(entity_name)
        if not es:
            for key, val in entity_stats.items():
                if entity_name.lower() in key.lower() or key.lower() in entity_name.lower():
                    es = val
                    break

        if es:
            lowest_pct = round((es["lowest_wins"] / es["total_with_lowest"]) * 100, 1) if es["total_with_lowest"] > 0 else None
            top_winners = [{"company": c, "wins": n} for c, n in es["comp_wins"].most_common(5)]
            summary["historical_awards"] = {
                "total_construction_awarded": es["total_awarded"],
                "total_value_awarded": round(es["total_value"], 2),
                "avg_winning_bid": round(es["total_value"] / es["total_awarded"], 2) if es["total_awarded"] > 0 else 0,
                "lowest_bidder_wins_pct": lowest_pct,
                "top_winners": top_winners,
            }
