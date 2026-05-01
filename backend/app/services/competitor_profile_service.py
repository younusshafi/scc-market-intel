"""Competitor behaviour profile service."""
import json, time, logging, re
from datetime import datetime
from collections import defaultdict

import requests
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import TenderProbe, CompetitorProfile
from app.services.competitive_intel_service import resolve_competitor, COMPETITORS

logger = logging.getLogger(__name__)

PROFILE_SYSTEM_PROMPT = """You are a competitive intelligence analyst for Sarooj Construction Company (SCC). Analyse each competitor's behaviour patterns from their tender participation data and produce strategic profiles.

For each competitor, write:
- behaviour_summary: 2-3 sentences describing their bidding pattern, speed of entry, price positioning, and strategic intent
- threat_level: "high", "medium", "low" based on how often they compete with SCC and their win potential
- scc_strategy: 1 sentence recommendation for how SCC should respond when this competitor is present

Be specific — reference actual numbers, tender names, and patterns. Do not use generic language.
Respond in JSON only. Return {"profiles": [...]}"""


def _call_groq_json(system_prompt, user_content):
    settings = get_settings()
    if not settings.groq_api_key:
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
    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=90)
    except requests.RequestException as e:
        logger.error(f"Groq API failed: {e}")
        return None
    if r.status_code != 200:
        logger.error(f"Groq {r.status_code}: {r.text[:300]}")
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
        return None


def build_competitor_profiles(db: Session) -> dict:
    """Build AI-powered competitor behaviour profiles from probe data."""
    probes = db.query(TenderProbe).all()
    if not probes:
        return {"status": "no_data", "built": 0}

    # Gather per-competitor activity
    comp_data = {name: {"docs": [], "bids": [], "withdrawals": [], "categories": [], "tenders_with_scc": []}
                 for name in COMPETITORS if name != "Sarooj"}

    for probe in probes:
        bidders = probe.bidders or []
        purchasers = probe.purchasers or []
        nit = probe.nit or {}

        bid_companies = set()
        doc_companies = set()

        for b in bidders:
            name = resolve_competitor(b.get("company", ""))
            if name:
                bid_companies.add(name)
                if name != "Sarooj" and name in comp_data:
                    comp_data[name]["bids"].append({
                        "tender": probe.tender_number,
                        "name": probe.tender_name or "",
                        "value": b.get("quoted_value", ""),
                        "category": probe.category or "",
                        "governorate": nit.get("governorate", ""),
                    })

        for p in purchasers:
            name = resolve_competitor(p.get("company", ""))
            if name:
                doc_companies.add(name)
                if name != "Sarooj" and name in comp_data:
                    comp_data[name]["docs"].append({
                        "tender": probe.tender_number,
                        "name": probe.tender_name or "",
                        "date": p.get("purchase_date", ""),
                        "category": probe.category or "",
                        "governorate": nit.get("governorate", ""),
                    })

        # Withdrawals: purchased docs but didn't bid
        for name in doc_companies:
            if name != "Sarooj" and name not in bid_companies and name in comp_data:
                comp_data[name]["withdrawals"].append(probe.tender_number)

        # SCC overlap: Sarooj present as bidder OR doc purchaser
        sarooj_present = "Sarooj" in bid_companies or "Sarooj" in doc_companies
        for name in (bid_companies | doc_companies):
            if name != "Sarooj" and sarooj_present and name in comp_data:
                comp_data[name]["tenders_with_scc"].append(probe.tender_number)

        # Categories
        if probe.category:
            for name in (bid_companies | doc_companies):
                if name in comp_data:
                    comp_data[name]["categories"].append(probe.category)

    # Build summary stats for each competitor
    competitor_summaries = []
    for comp_name, data in comp_data.items():
        if comp_name == "Sarooj":
            continue  # SCC is Sarooj — never profile ourselves
        if not data["docs"] and not data["bids"]:
            continue
        docs_count = len(data["docs"])
        bids_count = len(data["bids"])
        conv_rate = round(bids_count / max(docs_count, 1) * 100)
        withdrawals = len(data["withdrawals"])
        scc_overlap = len(set(data["tenders_with_scc"]))

        # Top categories
        cat_counts = defaultdict(int)
        for cat in data["categories"]:
            cat_counts[cat] += 1
        top_cats = sorted(cat_counts.items(), key=lambda x: -x[1])[:3]

        # Top governorates
        gov_counts = defaultdict(int)
        for d in data["docs"] + data["bids"]:
            gov = d.get("governorate", "")
            if gov:
                gov_counts[gov] += 1
        top_govs = sorted(gov_counts.items(), key=lambda x: -x[1])[:3]

        summary = {
            "competitor": comp_name,
            "docs_purchased": docs_count,
            "bids_submitted": bids_count,
            "conversion_rate": conv_rate,
            "withdrawals": withdrawals,
            "scc_overlap": scc_overlap,
            "top_categories": [c[0] for c in top_cats],
            "top_governorates": [g[0] for g in top_govs],
            "recent_bids": [{"tender": b["tender"], "name": b["name"][:50], "value": b["value"]} for b in data["bids"][:5]],
        }
        competitor_summaries.append(summary)

    if not competitor_summaries:
        return {"status": "no_competitor_data", "built": 0}

    # Call LLM for strategic profiles
    user_content = json.dumps(competitor_summaries, ensure_ascii=False)
    result = _call_groq_json(PROFILE_SYSTEM_PROMPT, user_content)

    if not result:
        return {"status": "llm_failed", "built": 0}

    profiles = result if isinstance(result, list) else result.get("profiles", [])

    # Store in database
    built = 0
    for profile in profiles:
        comp_name = profile.get("competitor", "")
        if not comp_name:
            continue

        # Find matching stats
        stats = next((s for s in competitor_summaries if s["competitor"] == comp_name), {})

        existing = db.query(CompetitorProfile).filter_by(competitor_name=comp_name).first()
        if existing:
            existing.behaviour_summary = profile.get("behaviour_summary", "")
            existing.threat_level = profile.get("threat_level", "")
            existing.scc_strategy = profile.get("scc_strategy", "")
            existing.conversion_rate = stats.get("conversion_rate", 0)
            existing.overlap_with_scc = stats.get("scc_overlap", 0)
            existing.top_categories = stats.get("top_categories", [])
            existing.top_governorates = stats.get("top_governorates", [])
            existing.built_at = datetime.utcnow()
        else:
            db.add(CompetitorProfile(
                competitor_name=comp_name,
                behaviour_summary=profile.get("behaviour_summary", ""),
                threat_level=profile.get("threat_level", ""),
                scc_strategy=profile.get("scc_strategy", ""),
                conversion_rate=stats.get("conversion_rate", 0),
                overlap_with_scc=stats.get("scc_overlap", 0),
                top_categories=stats.get("top_categories", []),
                top_governorates=stats.get("top_governorates", []),
            ))
        built += 1

    db.commit()
    return {"status": "success", "built": built}
