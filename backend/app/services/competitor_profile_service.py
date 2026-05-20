"""Competitor behaviour profile service."""
import json, time, logging, os
from datetime import datetime
from collections import defaultdict

from sqlalchemy.orm import Session

from app.services.llm_client import call_llm_json
from app.models import TenderProbe, CompetitorProfile, AwardedTender
from app.services.competitive_intel_service import resolve_competitor, COMPETITORS

logger = logging.getLogger(__name__)

# Map competitive_intelligence.json keys → canonical COMPETITORS keys
_CI_NAME_MAP = {
    "Galfar": "Galfar",
    "Al Tasnim": "Al Tasnim",
    "Premier International Projects": "Premier International",
    "Strabag": "Strabag",
    "Towell": "Towell",
    "Larsen & Toubro": "L&T",
    "Arab Contractors": "Arab Contractors",
    "Ozkar": "Ozkar",
    "Hassan Allam": "Hassan Allam",
}

_CI_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "competitive_intelligence.json")


def _load_ci_context() -> dict:
    """Load per-competitor context from competitive_intelligence.json. Returns {} on any error."""
    try:
        with open(os.path.normpath(_CI_PATH), encoding="utf-8") as f:
            ci = json.load(f)
        profiles = ci.get("competitor_profiles", {})
        result = {}
        for ci_name, data in profiles.items():
            canonical = _CI_NAME_MAP.get(ci_name, ci_name)
            result[canonical] = {
                "total_bids": data.get("total_bids", 0),
                "wins": data.get("wins", 0),
                "win_rate_pct": round(data.get("wins", 0) / max(data.get("total_bids", 1), 1) * 100, 1),
                "genuine_band": data.get("genuine_band", "unknown"),
                "token_bid_rate_pct": round(data.get("token_bid_rate", 0) * 100, 1),
                "strategic_note": data.get("strategic_note", ""),
            }
        return result
    except Exception:
        return {}


PROFILE_SYSTEM_PROMPT = """You are a competitive intelligence analyst for Sarooj Construction Company (SCC), an Omani Tier-1 civil infrastructure contractor. Analyse each competitor from their tender participation data, historical award record, and competitive intelligence context.

Each competitor entry includes:
- probe_data: live tender participation (docs, bids, SCC overlap, recent bids)
- historical_awards: from 28,529 awarded tender records
- ci_context: pre-computed stats (total_bids, wins, win_rate_pct, genuine_band, token_bid_rate_pct, strategic_note)

For each competitor, produce:
- behaviour_summary: 2-3 sentences — reference their genuine_band (where they actually win), token_bid_rate_pct, historical win rate, and strategic pattern
- threat_level: "high", "medium", "low" — based on SCC overlap count, historical wins, and genuine band overlap with SCC (50M+)
- scc_strategy: 1 precise sentence — what SCC should do specifically when this competitor is present (reference their band, token rate, or entity territory)

Rules:
- Be specific — cite actual numbers (e.g. "43.5% token bid rate", "genuine band: 50M+", "11 historical wins")
- If token_bid_rate_pct > 40%: note they use token bids heavily and are not a serious pricing threat below their genuine band
- If genuine_band is "unknown": note limited data
- Do not use generic phrases like "poses a significant threat" without citing specifics

Respond in JSON only. Return {"profiles": [...]}"""



def build_competitor_profiles(db: Session) -> dict:
    """Build AI-powered competitor behaviour profiles from probe data."""
    # Load pre-computed competitive intelligence context
    ci_context = _load_ci_context()

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
        # Attach CI context (genuine band, token rate, win rate from 28K awards dataset)
        if comp_name in ci_context:
            summary["ci_context"] = ci_context[comp_name]

        competitor_summaries.append(summary)

    # Add CI-only competitors (no probe data but have CI stats) — ensures all 9 are included
    existing_names = {s["competitor"] for s in competitor_summaries}
    for ci_name, ci_data in ci_context.items():
        if ci_name not in existing_names and ci_name != "Sarooj":
            competitor_summaries.append({
                "competitor": ci_name,
                "docs_purchased": 0,
                "bids_submitted": 0,
                "conversion_rate": 0,
                "withdrawals": 0,
                "scc_overlap": 0,
                "top_categories": [],
                "top_governorates": [],
                "recent_bids": [],
                "ci_context": ci_data,
            })

    if not competitor_summaries:
        return {"status": "no_competitor_data", "built": 0}

    # Enrich with historical award data
    _enrich_with_award_history(db, competitor_summaries)

    # Call LLM for strategic profiles
    user_content = json.dumps(competitor_summaries, ensure_ascii=False)
    result = call_llm_json(PROFILE_SYSTEM_PROMPT, user_content)

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


def _enrich_with_award_history(db: Session, competitor_summaries: list):
    """Add historical award stats to competitor summaries for richer LLM context."""
    from collections import Counter

    try:
        awarded = db.query(AwardedTender).filter(
            AwardedTender.is_construction == True,
            AwardedTender.winner_company != None,
        ).all()
    except Exception:
        return  # Gracefully skip if table doesn't exist yet

    if not awarded:
        return

    # Build per-competitor historical stats
    comp_wins = Counter()
    comp_bids = Counter()
    comp_values = defaultdict(float)
    comp_entities = defaultdict(Counter)

    for t in awarded:
        winner = resolve_competitor(t.winner_company) if t.winner_company else None
        if winner:
            comp_wins[winner] += 1
            if t.winning_value:
                comp_values[winner] += t.winning_value
            if t.entity:
                comp_entities[winner][t.entity] += 1

        # Count bids from bidders_json
        if t.bidders_json:
            try:
                bidders = json.loads(t.bidders_json) if isinstance(t.bidders_json, str) else t.bidders_json
                seen = set()
                for b in (bidders if isinstance(bidders, list) else []):
                    comp = resolve_competitor(b.get("company", "") if isinstance(b, dict) else "")
                    if comp and comp not in seen:
                        seen.add(comp)
                        comp_bids[comp] += 1
            except (json.JSONDecodeError, TypeError):
                pass

    # Attach to each summary
    for summary in competitor_summaries:
        comp_name = summary.get("competitor", "")
        wins = comp_wins.get(comp_name, 0)
        bids = comp_bids.get(comp_name, 0)
        total_val = comp_values.get(comp_name, 0)
        top_ents = [{"entity": e, "wins": c} for e, c in comp_entities.get(comp_name, Counter()).most_common(3)]

        summary["historical_awards"] = {
            "total_bids": bids,
            "wins": wins,
            "win_rate_pct": round((wins / bids) * 100, 1) if bids > 0 else 0,
            "total_contract_value": round(total_val, 2),
            "avg_winning_bid": round(total_val / wins, 2) if wins > 0 else 0,
            "top_entities_won": top_ents,
        }
