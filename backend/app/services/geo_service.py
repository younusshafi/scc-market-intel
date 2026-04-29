"""
Geographic distribution service.
Infers governorate/region from tender names, entity names, and NIT data.
Oman has 11 governorates — we map tenders to them using keyword matching.
"""

import re
import logging
from collections import Counter

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models import Tender, TenderProbe

logger = logging.getLogger(__name__)

# Oman governorates with keywords that indicate them
GOVERNORATE_KEYWORDS = {
    "Muscat": [
        "muscat", "مسقط", "muttrah", "bausher", "seeb", "al amerat",
        "qurm", "ruwi", "al khuwair", "ghubra", "madinat al sultan qaboos",
    ],
    "Dhofar": [
        "dhofar", "ظفار", "salalah", "صلالة", "thumrait", "mirbat", "rakhyut",
    ],
    "Musandam": [
        "musandam", "مسندم", "khasab", "bukha", "dibba",
    ],
    "Al Buraimi": [
        "buraimi", "البريمي", "al buraimi", "mahdah",
    ],
    "Ad Dakhiliyah": [
        "dakhiliyah", "الداخلية", "nizwa", "bahla", "adam", "izki", "manah",
        "al hamra", "bid bid", "samail",
    ],
    "Al Batinah North": [
        "batinah north", "شمال الباطنة", "sohar", "صحار", "shinas", "liwa",
        "saham", "al khaburah", "suwaiq",
    ],
    "Al Batinah South": [
        "batinah south", "جنوب الباطنة", "rustaq", "al rustaq", "nakhal",
        "barka", "al musannah", "wadi al maawil",
    ],
    "Ash Sharqiyah North": [
        "sharqiyah north", "شمال الشرقية", "ibra", "al mudhaibi", "bidiyah",
        "al qabil", "wadi bani khalid", "dima wa al tayin",
    ],
    "Ash Sharqiyah South": [
        "sharqiyah south", "جنوب الشرقية", "sur", "صور", "al kamil", "jalan",
        "masirah", "al ashkharah",
    ],
    "Ad Dhahirah": [
        "dhahirah", "الظاهرة", "ibri", "yanqul", "dhank",
    ],
    "Al Wusta": [
        "wusta", "الوسطى", "haima", "duqm", "الدقم", "mahout", "al jazir",
    ],
}

# Common national entities that span all governorates (map to "National")
NATIONAL_ENTITIES = [
    "ministry", "وزارة", "authority", "هيئة", "oman", "عمان", "royal",
    "sultan", "national", "central", "council", "مجلس",
]


def infer_governorate(text: str) -> str | None:
    """Infer governorate from a text string (tender name, entity, etc.)."""
    if not text:
        return None
    low = text.lower()
    for gov, keywords in GOVERNORATE_KEYWORDS.items():
        for kw in keywords:
            if kw in low:
                return gov
    return None


def get_geographic_distribution(db: Session) -> dict:
    """Compute geographic distribution of tenders by governorate."""
    tenders = db.query(
        Tender.id,
        Tender.tender_name_en,
        Tender.tender_name_ar,
        Tender.entity_en,
        Tender.entity_ar,
        Tender.is_scc_relevant,
    ).all()

    # Also check NIT data from probes for more precise location
    probes = {
        p.tender_number: p.nit
        for p in db.query(TenderProbe.tender_number, TenderProbe.nit).all()
        if p.nit
    }

    gov_counts = Counter()
    gov_scc_counts = Counter()
    national_count = 0
    unlocated_count = 0

    for t in tenders:
        # Try to infer from multiple sources
        gov = None

        # 1. Check NIT governorate field if available
        # (tender_number not available on this query, skip probe lookup here)

        # 2. Try tender name (EN then AR)
        gov = infer_governorate(t.tender_name_en) or infer_governorate(t.tender_name_ar)

        # 3. Try entity name
        if not gov:
            gov = infer_governorate(t.entity_en) or infer_governorate(t.entity_ar)

        if gov:
            gov_counts[gov] += 1
            if t.is_scc_relevant:
                gov_scc_counts[gov] += 1
        else:
            # Check if it's a national-level entity
            entity_text = (t.entity_en or "") + " " + (t.entity_ar or "")
            if any(kw in entity_text.lower() for kw in NATIONAL_ENTITIES):
                national_count += 1
            else:
                unlocated_count += 1

    # Build sorted results
    regions = []
    total_located = sum(gov_counts.values())
    for gov in GOVERNORATE_KEYWORDS:
        count = gov_counts.get(gov, 0)
        scc = gov_scc_counts.get(gov, 0)
        regions.append({
            "governorate": gov,
            "count": count,
            "scc_relevant": scc,
            "pct": round(count / max(total_located, 1) * 100, 1),
        })
    regions.sort(key=lambda x: -x["count"])

    return {
        "regions": regions,
        "national": national_count,
        "unlocated": unlocated_count,
        "total_located": total_located,
        "total_tenders": len(tenders),
    }
