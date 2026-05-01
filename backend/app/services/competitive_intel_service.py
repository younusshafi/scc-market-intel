"""
Competitive intelligence service.
Processes probed tender data into dashboard-ready structures:
  - Major project cards
  - Head-to-head bid comparisons
  - Live competitive tenders
  - Competitor activity summary
"""

import logging
from sqlalchemy.orm import Session

from app.models import TenderProbe

logger = logging.getLogger(__name__)

COMPETITORS = {
    "Sarooj": ["sarooj", "سروج", "saroj"],
    "Galfar": ["galfar"],
    "Strabag": ["strabag"],
    "Al Tasnim": ["tasnim"],
    "L&T": ["l&t", "larsen", "l & t", "l and t"],
    "Towell": ["towell", "tawel"],
    "Hassan Allam": ["hassan allam", "hassanallam"],
    "Arab Contractors": ["arab contractor"],
    "Ozkar": ["ozkar"],
}

TRACKED_ALIASES = {
    "SAROOJ CONSTRUCTION COMPANY": "Sarooj",
    "Sarooj Construction Company": "Sarooj",
    "GALFAR ENGINEERING AND CONTRACTING": "Galfar",
    "STRABAG OMAN": "Strabag",
    "AL TASNIM ENTERPRISES": "Al Tasnim",
    "LARSEN AND TOUBRO (OMAN)": "L&T",
    "LARSEN AND TOUBRO": "L&T",
    "TOWELL CONSTRUCTION AND CO LLC": "Towell",
    "TOWELL INFRASTRUCTURE PROJECTS CO": "Towell",
    "HASSAN ALLAM CONSTRUCTION": "Hassan Allam",
    "Hassan Allam Construction": "Hassan Allam",
    "HASSAN ALLAM CONTRACTING AND CONSTRUCTION": "Hassan Allam",
    "THE ARAB CONTRACTORS OMAN LIMITED": "Arab Contractors",
    "The Arab Contractors Oman Limited": "Arab Contractors",
    "OZKAR": "Ozkar",
}


def resolve_competitor(company_name: str) -> str | None:
    """Map a company name to a tracked competitor short name, or None."""
    # Try exact alias match first
    if company_name in TRACKED_ALIASES:
        return TRACKED_ALIASES[company_name]
    # Then keyword matching
    low = company_name.lower()
    for comp, keywords in COMPETITORS.items():
        if any(kw in low for kw in keywords):
            return comp
    return None


def build_competitive_intel(db: Session) -> dict:
    """Build competitive intelligence from probed tender data."""
    probes = db.query(TenderProbe).all()

    if not probes:
        return {
            "major_projects": [],
            "head_to_head": [],
            "live_competitive": [],
            "activity_summary": [],
            "total_probed": 0,
        }

    major_projects = []
    head_to_head = []
    live_competitive = []

    # Activity tracker
    activity = {comp: {"docs": 0, "bids": 0, "max_bid": 0} for comp in COMPETITORS}
    # Track per-competitor tender sets for withdrawal detection
    comp_bid_tenders = {comp: set() for comp in COMPETITORS}
    comp_doc_tenders = {comp: set() for comp in COMPETITORS}

    for probe in probes:
        fee = probe.fee or 0
        bidders = probe.bidders or []
        purchasers = probe.purchasers or []
        nit = probe.nit or {}

        # --- Update activity tracker ---
        seen_bid = set()
        seen_doc = set()
        for b in bidders:
            name = resolve_competitor(b.get("company", ""))
            if name and name in activity and name not in seen_bid:
                seen_bid.add(name)
                activity[name]["bids"] += 1
                comp_bid_tenders[name].add(probe.tender_number)
                try:
                    val = float(b.get("quoted_value", 0) or 0)
                except (ValueError, TypeError):
                    val = 0
                if val > activity[name]["max_bid"]:
                    activity[name]["max_bid"] = val
        for p in purchasers:
            name = resolve_competitor(p.get("company", ""))
            if name and name in activity and name not in seen_doc:
                seen_doc.add(name)
                activity[name]["docs"] += 1
                comp_doc_tenders[name].add(probe.tender_number)

        # --- Major Projects (fee >= 200 OMR, SCC category OR has tracked competitors) ---
        SCC_CAT_KW = ["construction", "ports", "roads", "bridges", "pipeline",
                      "electromechanical", "dams", "marine", "مقاولات"]
        cat_lower = (probe.category or "").lower()
        is_scc_cat = any(kw in cat_lower for kw in SCC_CAT_KW)

        if fee >= 200:
            comp_bids = {}
            comp_docs = {}
            for b in bidders:
                name = resolve_competitor(b.get("company", ""))
                if name:
                    try:
                        fval = float(b.get("quoted_value", 0) or 0)
                    except (ValueError, TypeError):
                        fval = 0
                    comp_bids[name] = {"value": fval, "status": b.get("status", "")}
            for p in purchasers:
                name = resolve_competitor(p.get("company", ""))
                if name:
                    comp_docs[name] = p.get("purchase_date", "")

            all_comp_names = set(list(comp_bids.keys()) + list(comp_docs.keys()))
            comp_presence = []
            for c in all_comp_names:
                role = "BID" if c in comp_bids else "DOCS"
                comp_presence.append({
                    "name": c, "role": role,
                    "value": comp_bids.get(c, {}).get("value", 0),
                })

            num_bidders = len(bidders)
            num_purchasers = len(purchasers)

            if num_bidders >= 10:
                border_colour = "#EF4444"
            elif num_bidders >= 5:
                border_colour = "#F59E0B"
            else:
                border_colour = "#10B981"

            # Only include if SCC category OR has tracked competitors
            has_competitors = len(all_comp_names) > 0
            if is_scc_cat or has_competitors:
                major_projects.append({
                    "name": nit.get("title", "") or probe.tender_name or "",
                    "entity": probe.entity or "",
                    "fee": fee,
                    "category": probe.category or "",
                    "tender_number": probe.tender_number,
                    "num_bidders": num_bidders,
                    "num_purchasers": num_purchasers,
                    "competitors": comp_presence,
                    "sarooj_present": "Sarooj" in all_comp_names,
                    "border_colour": border_colour,
                })

        # --- Head-to-Head (Sarooj bid vs competitor bids) ---
        sarooj_val = None
        comp_vals = []
        for b in bidders:
            name = resolve_competitor(b.get("company", ""))
            try:
                val = float(b.get("quoted_value", 0) or 0)
            except (ValueError, TypeError):
                val = 0
            if name == "Sarooj" and val > 0:
                sarooj_val = val
            elif name and name != "Sarooj" and val > 0:
                comp_vals.append({"name": name, "value": val})
        if sarooj_val and comp_vals:
            rows = [{"name": "Sarooj (SCC)", "value": sarooj_val, "diff": 0, "diff_pct": 0, "is_scc": True}]
            for c in sorted(comp_vals, key=lambda x: x["value"]):
                diff = round(c["value"] - sarooj_val, 2)
                diff_pct = round(diff / sarooj_val * 100, 1)
                rows.append({"name": c["name"], "value": c["value"],
                             "diff": diff, "diff_pct": diff_pct, "is_scc": False})
            head_to_head.append({
                "project": nit.get("title", "") or probe.tender_name or "",
                "tender_number": probe.tender_number,
                "rows": rows,
            })

        # --- Live Competitive (2+ tracked competitors purchased docs) ---
        tracked_in = []
        for p in purchasers:
            name = resolve_competitor(p.get("company", ""))
            if name:
                tracked_in.append({"name": name, "date": p.get("purchase_date", "")})
        if len(tracked_in) >= 2:
            live_competitive.append({
                "project": nit.get("title", "") or probe.tender_name or "",
                "tender_number": probe.tender_number,
                "total_purchasers": len(purchasers),
                "tracked": tracked_in,
                "tracked_count": len(tracked_in),
                "has_bids": len(bidders) > 0,
            })

    # Sort outputs
    major_projects.sort(key=lambda x: -x["fee"])
    live_competitive.sort(key=lambda x: -x["tracked_count"])

    # Build activity summary with withdrawal detection
    activity_summary = []
    for comp, d in activity.items():
        conv = round(d["bids"] / max(d["docs"], 1) * 100) if d["docs"] else 0
        # Withdrawal: purchased docs but did not bid
        withdrew_from = comp_doc_tenders[comp] - comp_bid_tenders[comp]
        activity_summary.append({
            "name": comp, "docs": d["docs"], "bids": d["bids"],
            "conv": conv, "max_bid": d["max_bid"],
            "withdrawals": len(withdrew_from),
            "withdrew_from": list(withdrew_from),
        })
    activity_summary.sort(key=lambda x: -(x["docs"] + x["bids"]))

    return {
        "major_projects": major_projects,
        "head_to_head": head_to_head,
        "live_competitive": live_competitive,
        "activity_summary": activity_summary,
        "total_probed": len(probes),
    }
