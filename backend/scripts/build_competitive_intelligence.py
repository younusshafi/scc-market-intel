"""
Build competitive intelligence JSON from awarded_tenders.csv analysis.
Run from repo root: python backend/scripts/build_competitive_intelligence.py
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
CSV_DIR = REPO_ROOT / "scraped_data" / "analysis"
ANALYSIS_DIR = REPO_ROOT / "scraped_data" / "analysis"
OUTPUT_DIR = REPO_ROOT / "backend" / "data"

AWARDED_CSV = CSV_DIR / "awarded_tenders.csv"
OUTPUT_JSON = OUTPUT_DIR / "competitive_intelligence.json"
SCC_BIDS_JSON = ANALYSIS_DIR / "scc_bids_extracted.json"
COMPETITOR_BIDS_JSON = ANALYSIS_DIR / "competitor_bids_classified.json"

# ---------------------------------------------------------------------------
# Competitor definitions
# ---------------------------------------------------------------------------
COMPETITOR_KEYWORDS = {
    "Galfar": ["GALFAR"],
    "Al Tasnim": ["TASNIM"],
    "Premier International Projects": ["PREMIER INTERNATIONAL"],
    "Strabag": ["STRABAG"],
    "Towell": ["TOWELL"],
    "Larsen & Toubro": ["LARSEN"],
    "Arab Contractors": ["ARAB CONTRACTORS"],
    "Ozkar": ["OZKAR"],
    "Hassan Allam": ["HASSAN ALLAM"],
}

# Size bands (OMR)
SIZE_BANDS = [
    ("under_1M", 0, 1_000_000),
    ("1M_5M", 1_000_000, 5_000_000),
    ("5M_15M", 5_000_000, 15_000_000),
    ("15M_50M", 15_000_000, 50_000_000),
    ("50M_plus", 50_000_000, float("inf")),
]


# ---------------------------------------------------------------------------
# Stage 2 — SCC Bid Extraction
# ---------------------------------------------------------------------------

def extract_scc_bids(df: pd.DataFrame) -> list[dict]:
    """Extract all bid records where SCC (SAROOJ or SCC) appears in bidders_json."""
    records = []
    rows_with_bidders = df[df["bidders_json"].notna()]

    for _, row in rows_with_bidders.iterrows():
        try:
            bidders = json.loads(row["bidders_json"])
        except (json.JSONDecodeError, TypeError):
            continue

        # Find all SCC entries (may appear multiple times in JV tenders)
        scc_bidders = []
        for b in bidders:
            company = str(b.get("company", "")).upper()
            if "SAROOJ" in company or (
                "SCC" in company
                and "SUCCESSFUL" not in company
                and "ACCESSORIES" not in company
            ):
                scc_bidders.append(b)

        if not scc_bidders:
            continue

        # Find winner company name (shared across all SCC entries in this tender)
        winner_company = None
        for b in bidders:
            if b.get("is_winner"):
                winner_company = b.get("company")
                break
        if winner_company is None:
            winner_company = row.get("winner_company")

        # Compute scc_rank helpers (shared)
        valid_bids = [
            b for b in bidders
            if b.get("quoted_value") is not None and float(b.get("quoted_value", 0) or 0) > 0
        ]
        sorted_bids = sorted(valid_bids, key=lambda b: float(b.get("quoted_value", 0)))

        winning_value = row.get("winning_value")

        for scc_bidder in scc_bidders:
            scc_bid = scc_bidder.get("quoted_value")
            scc_won = bool(scc_bidder.get("is_winner", False))

            # Compute gap_pct — only for losses with valid values
            gap_pct = None
            if not scc_won and scc_bid and winning_value and float(scc_bid) > 0 and float(winning_value) > 0:
                gap_pct = round(
                    (float(scc_bid) - float(winning_value)) / float(winning_value) * 100, 2
                )

            # Compute scc_rank — rank by quoted_value (1 = lowest)
            scc_rank = None
            if scc_bid and float(scc_bid) > 0:
                for rank, b in enumerate(sorted_bids, 1):
                    if str(b.get("company", "")).upper() == str(scc_bidder.get("company", "")).upper():
                        scc_rank = rank
                        break

            records.append({
                "tender_title": row.get("tender_title"),
                "entity": row.get("entity"),
                "category": row.get("category"),
                "awarded_date": str(row.get("awarded_date", "")),
                "scc_company": scc_bidder.get("company"),
                "scc_bid": float(scc_bid) if scc_bid else None,
                "scc_won": scc_won,
                "winning_value": float(winning_value) if winning_value else None,
                "gap_pct": gap_pct,
                "scc_rank": scc_rank,
                "num_bidders": len(bidders),
                "winner_company": winner_company,
            })

    return records


# ---------------------------------------------------------------------------
# Stage 3 — Token Bid Classification
# ---------------------------------------------------------------------------

def classify_bid_intent(gap_pct) -> str | None:
    """Classify a bid loss by gap_pct into TOKEN / NEAR_MISS / COMPETITIVE / BORDERLINE."""
    if gap_pct is None:
        return None
    if gap_pct > 50:
        return "TOKEN"
    if gap_pct <= 10:
        return "NEAR_MISS"
    if gap_pct <= 25:
        return "COMPETITIVE"
    # 25 < gap_pct <= 50
    return "BORDERLINE"


def extract_competitor_bids(df: pd.DataFrame, keywords: list[str]) -> list[dict]:
    """Extract all bid records for a competitor identified by keyword list."""
    records = []
    rows_with_bidders = df[df["bidders_json"].notna()]

    for _, row in rows_with_bidders.iterrows():
        try:
            bidders = json.loads(row["bidders_json"])
        except (json.JSONDecodeError, TypeError):
            continue

        winning_value = row.get("winning_value")
        for b in bidders:
            company = str(b.get("company", "")).upper()
            matched = any(kw in company for kw in keywords)
            if not matched:
                continue

            bid_value = b.get("quoted_value")
            is_won = bool(b.get("is_winner", False))

            gap_pct = None
            if not is_won and bid_value and winning_value and float(bid_value) > 0 and float(winning_value) > 0:
                gap_pct = round(
                    (float(bid_value) - float(winning_value)) / float(winning_value) * 100, 2
                )

            records.append({
                "company": b.get("company"),
                "tender_title": row.get("tender_title"),
                "entity": row.get("entity"),
                "category": row.get("category"),
                "awarded_date": str(row.get("awarded_date", "")),
                "bid_value": float(bid_value) if bid_value else None,
                "is_won": is_won,
                "winning_value": float(winning_value) if winning_value else None,
                "gap_pct": gap_pct,
                "intent": classify_bid_intent(gap_pct) if not is_won else "WIN",
            })

    return records


def classify_all_competitor_bids(df: pd.DataFrame) -> dict:
    """Extract and classify bids for all tracked competitors."""
    result = {}
    for name, keywords in COMPETITOR_KEYWORDS.items():
        bids = extract_competitor_bids(df, keywords)
        wins = sum(1 for b in bids if b["is_won"])
        losses = [b for b in bids if not b["is_won"] and b["gap_pct"] is not None]
        token_count = sum(1 for b in losses if b["intent"] == "TOKEN")
        token_rate = round(token_count / len(losses), 3) if losses else 0.0

        result[name] = {
            "keywords": keywords,
            "total_bids": len(bids),
            "wins": wins,
            "win_rate": round(wins / len(bids), 3) if bids else 0.0,
            "token_bid_count": token_count,
            "token_bid_rate": token_rate,
            "bids": bids,
        }
        print(
            f"  {name:40s} bids={len(bids):4d}  wins={wins:3d}  token_rate={token_rate:.0%}"
        )
    return result


# ---------------------------------------------------------------------------
# Stage 4 — Competitor Band Analysis
# ---------------------------------------------------------------------------

def get_band(value) -> str | None:
    """Return band name for a given OMR value."""
    if value is None or value <= 0:
        return None
    for band_name, low, high in SIZE_BANDS:
        if low <= value < high:
            return band_name
    return "50M_plus"


def analyze_competitor_bands(competitor_data: dict, scc_bids: list[dict]) -> dict:
    """Compute genuine-bid band analysis per competitor + SCC."""
    band_names = [b[0] for b in SIZE_BANDS]
    result = {}

    # Build SCC data in same format
    all_subjects = {}
    scc_records = []
    for r in scc_bids:
        intent = classify_bid_intent(r["gap_pct"]) if not r["scc_won"] else "WIN"
        scc_records.append({
            "bid_value": r["scc_bid"],
            "is_won": r["scc_won"],
            "gap_pct": r["gap_pct"],
            "intent": intent,
            "winning_value": r["winning_value"],
        })
    all_subjects["SCC"] = scc_records

    for name, data in competitor_data.items():
        all_subjects[name] = [
            {"bid_value": b["bid_value"], "is_won": b["is_won"],
             "gap_pct": b["gap_pct"], "intent": b["intent"],
             "winning_value": b["winning_value"]}
            for b in data["bids"]
        ]

    for subject, bids in all_subjects.items():
        band_stats = {bn: {"genuine_bids": 0, "wins": 0} for bn in band_names}

        for b in bids:
            val = b["bid_value"] if b["bid_value"] else b["winning_value"]
            band = get_band(val)
            if band is None:
                continue
            is_genuine = b["is_won"] or b["intent"] in ("WIN", "NEAR_MISS", "COMPETITIVE", "BORDERLINE")
            is_token = b["intent"] == "TOKEN"
            if is_genuine and not is_token:
                band_stats[band]["genuine_bids"] += 1
            if b["is_won"]:
                band_stats[band]["wins"] += 1

        # Compute win rates
        for bn in band_names:
            s = band_stats[bn]
            s["win_rate"] = round(s["wins"] / s["genuine_bids"], 3) if s["genuine_bids"] > 0 else 0.0

        # Genuine band = band with highest genuine win rate (min 3 genuine bids to qualify)
        # Tie-break: prefer larger bands (higher index = larger value band)
        # This identifies where the entity is most strategically competitive
        qualified = [bn for bn in band_names if band_stats[bn]["genuine_bids"] >= 3]
        if qualified:
            genuine_band = max(
                qualified,
                key=lambda bn: (band_stats[bn]["win_rate"], band_names.index(bn))
            )
        else:
            # Fallback: band with most genuine bids
            genuine_band = max(band_names, key=lambda bn: band_stats[bn]["genuine_bids"])
            if band_stats[genuine_band]["genuine_bids"] == 0:
                genuine_band = "unknown"

        result[subject] = {
            "by_band": band_stats,
            "genuine_band": genuine_band,
        }

    return result


def analyze_competitor_overall(competitor_data: dict) -> dict:
    """Per-competitor overall stats."""
    result = {}
    for name, data in competitor_data.items():
        bids = data["bids"]
        wins = data["wins"]
        bid_values = [b["bid_value"] for b in bids if b["bid_value"] and b["bid_value"] > 0]
        winning_values = [b["winning_value"] for b in bids if b["is_won"] and b["winning_value"] and b["winning_value"] > 0]
        result[name] = {
            "total_bids": len(bids),
            "wins": wins,
            "overall_win_rate": data["win_rate"],
            "avg_bid_value": round(sum(bid_values) / len(bid_values)) if bid_values else None,
            "avg_winning_bid_omr": round(sum(winning_values) / len(winning_values)) if winning_values else None,
        }
    return result


# ---------------------------------------------------------------------------
# Stage 5 — Entity Intelligence
# ---------------------------------------------------------------------------

def analyze_entity_patterns(scc_bids: list[dict], competitor_data: dict) -> tuple[dict, dict]:
    """Analyze per-entity patterns for SCC appearances."""
    from collections import defaultdict

    entity_records: dict[str, list] = defaultdict(list)
    for r in scc_bids:
        entity_records[str(r["entity"])].append(r)

    entity_intel = {}
    for entity, records in entity_records.items():
        total = len(records)
        wins = sum(1 for r in records if r["scc_won"])
        win_rate = round(wins / total, 3) if total > 0 else 0.0

        losses = [r for r in records if not r["scc_won"] and r["gap_pct"] is not None]
        competitive_losses = [r for r in losses if classify_bid_intent(r["gap_pct"]) != "TOKEN"]
        avg_gap = round(sum(r["gap_pct"] for r in competitive_losses) / len(competitive_losses), 1) if competitive_losses else None
        near_misses = sum(1 for r in losses if r["gap_pct"] is not None and 0 <= r["gap_pct"] <= 10)

        # Find competitors who beat SCC here
        rivals = []
        for r in losses:
            wc = r.get("winner_company")
            if wc and str(wc).upper() not in ("", "NONE", "NAN"):
                rivals.append(str(wc))

        # Dominant rivals (most frequent)
        from collections import Counter
        rival_counts = Counter(rivals)
        dominant = [name for name, _ in rival_counts.most_common(3)]

        entity_intel[entity] = {
            "bids": total,
            "wins": wins,
            "win_rate": win_rate,
            "avg_gap_pct": avg_gap,
            "near_misses": near_misses,
            "dominant_rivals": dominant,
        }

    # Build threat map
    threat_map = {}
    for entity, intel in entity_intel.items():
        if intel["wins"] == 0 and intel["bids"] >= 3:
            threat_level = "HIGH"
        elif intel["win_rate"] >= 0.3:
            threat_level = "LOW"
        else:
            threat_level = "MEDIUM"

        primary = intel["dominant_rivals"][:2] if intel["dominant_rivals"] else []
        avg_gap_str = f"{intel['avg_gap_pct']:.0f}%" if intel["avg_gap_pct"] is not None else "n/a"
        threat_map[entity] = {
            "primary_threats": primary,
            "threat_level": threat_level,
            "note": f"SCC {intel['wins']} wins from {intel['bids']} bids. Avg gap (competitive losses): {avg_gap_str}.",
        }

    return entity_intel, threat_map


def find_near_misses(scc_bids: list[dict]) -> list[dict]:
    """Return all SCC losses where gap_pct is between 0 and 10% (SCC bid slightly above winner).
    Negative gap_pct (SCC bid below winner but didn't win) excluded — likely JV or disqualification cases.
    """
    near_misses = [
        r for r in scc_bids
        if not r["scc_won"] and r["gap_pct"] is not None and 0 <= r["gap_pct"] <= 10
    ]
    near_misses.sort(key=lambda r: r["gap_pct"])
    return [
        {
            "tender_title": r["tender_title"],
            "entity": r["entity"],
            "scc_bid": r["scc_bid"],
            "winning_value": r["winning_value"],
            "gap_pct": r["gap_pct"],
            "winner_company": r["winner_company"],
            "awarded_date": r["awarded_date"],
        }
        for r in near_misses
    ]


# ---------------------------------------------------------------------------
# Stage 6 — Assemble competitive_intelligence.json
# ---------------------------------------------------------------------------

def assemble_intelligence(
    scc_bids: list[dict],
    competitor_data: dict,
    band_analysis: dict,
    overall_stats: dict,
    entity_intel: dict,
    threat_map: dict,
    near_misses: list[dict],
) -> dict:
    """Assemble the full competitive_intelligence.json structure."""

    total_scc = len(scc_bids)
    scc_wins_total = sum(1 for r in scc_bids if r["scc_won"])
    overall_win_rate = round(scc_wins_total / total_scc, 3) if total_scc > 0 else 0.0

    scc_band = band_analysis.get("SCC", {})
    genuine_band = scc_band.get("genuine_band", "unknown")
    genuine_band_stats = scc_band.get("by_band", {}).get(genuine_band, {})
    genuine_band_win_rate = genuine_band_stats.get("win_rate", 0.0)

    # Token bid rates for SCC
    scc_losses = [r for r in scc_bids if not r["scc_won"] and r["gap_pct"] is not None]
    scc_token_count = sum(1 for r in scc_losses if r["gap_pct"] > 50)
    scc_token_rate = round(scc_token_count / len(scc_losses), 3) if scc_losses else 0.0

    # Token rate in 5M-15M band
    scc_5_15 = [r for r in scc_losses if r["scc_bid"] and 5_000_000 <= float(r["scc_bid"]) < 15_000_000]
    scc_token_5_15 = sum(1 for r in scc_5_15 if r["gap_pct"] > 50)
    scc_token_rate_5_15 = round(scc_token_5_15 / len(scc_5_15), 3) if scc_5_15 else 0.0

    # Band details for SCC
    by_size_band = {}
    for bn, _, _ in SIZE_BANDS:
        bs = scc_band.get("by_band", {}).get(bn, {})
        by_size_band[bn] = {
            "genuine_bids": bs.get("genuine_bids", 0),
            "wins": bs.get("wins", 0),
            "win_rate": bs.get("win_rate", 0.0),
        }

    # Build competitor profiles
    competitor_profiles = {}
    profile_meta = {
        "Galfar": {
            "search_keywords": ["GALFAR"],
            "genuine_band": band_analysis.get("Galfar", {}).get("genuine_band", "unknown"),
            "territory": ["Ministry of Transport", "Sultan Qaboos University", "Ministry of Health", "DUQM"],
            "strategic_note": "Capacity constrained — OMR 745M backlog, bid volume declining 9 in 2023 to 5 in 2025. Likely to price high. Not competing in SCC real territory below OMR 20M.",
        },
        "Al Tasnim": {
            "search_keywords": ["TASNIM"],
            "genuine_band": band_analysis.get("Al Tasnim", {}).get("genuine_band", "unknown"),
            "territory": ["North Al Batinah Governor Office", "Al Dakhiliyah Governor Office", "Muscat Municipality"],
            "strategic_note": "Owns Governor Office internal roads. Above OMR 15M almost always token bids. 2025 best year at 43% win rate. SCC cannot compete on cost in their core territory.",
        },
        "Premier International Projects": {
            "search_keywords": ["PREMIER INTERNATIONAL"],
            "genuine_band": band_analysis.get("Premier International Projects", {}).get("genuine_band", "unknown"),
            "territory": ["Ministry of Agricultural/Fisheries/Water Resources", "Musandam Governor Office", "Buraimi Governor Office", "North/South Sharqiyah Governor Office", "Al Dakhiliyah Governor Office"],
            "strategic_note": "WARNING: Not currently on SCC watchlist. Highest win rate of any competitor. Most disciplined pricing. Beats SCC on every head-to-head. Specialist in water, dams, flood protection, agricultural infrastructure. Should be Tier 1 watchlist.",
        },
        "Strabag": {
            "search_keywords": ["STRABAG"],
            "genuine_band": band_analysis.get("Strabag", {}).get("genuine_band", "unknown"),
            "territory": ["DUQM", "Public Authority for Special Economic Zones", "Ministry of Transport"],
            "strategic_note": "Most disciplined competitor. When they enter they intend to win. Surging in 2025 — 3 bids in 2024, 10 in 2025. Watch for increasing competition on large infrastructure.",
        },
        "Towell": {
            "search_keywords": ["TOWELL"],
            "genuine_band": band_analysis.get("Towell", {}).get("genuine_band", "unknown"),
            "territory": ["Ministry of Housing", "large selective contracts"],
            "strategic_note": "Selective bidder. Low token rate. When they appear, take seriously.",
        },
        "Larsen & Toubro": {
            "search_keywords": ["LARSEN"],
            "genuine_band": band_analysis.get("Larsen & Toubro", {}).get("genuine_band", "unknown"),
            "strategic_note": "Very low activity in Oman public tenders. International presence.",
        },
        "Arab Contractors": {
            "search_keywords": ["ARAB CONTRACTORS"],
            "genuine_band": band_analysis.get("Arab Contractors", {}).get("genuine_band", "unknown"),
            "strategic_note": "Low activity, Egyptian firm.",
        },
        "Ozkar": {
            "search_keywords": ["OZKAR"],
            "genuine_band": band_analysis.get("Ozkar", {}).get("genuine_band", "unknown"),
            "strategic_note": "Turkish firm. High token bid rate. Not a genuine threat.",
        },
        "Hassan Allam": {
            "search_keywords": ["HASSAN ALLAM"],
            "genuine_band": band_analysis.get("Hassan Allam", {}).get("genuine_band", "unknown"),
            "strategic_note": "Minimal Oman activity.",
        },
    }

    # Build head-to-head for SCC vs each competitor
    def head_to_head(competitor_name, keywords):
        """Count contests where both SCC and competitor appear in the same tender."""
        contests = 0
        scc_wins_hth = 0
        comp_wins_hth = 0
        scc_tender_titles = {r["tender_title"] for r in scc_bids}
        comp_data = competitor_data.get(competitor_name, {})
        for b in comp_data.get("bids", []):
            if b["tender_title"] in scc_tender_titles:
                contests += 1
                # find corresponding SCC bid
                scc_match = next((r for r in scc_bids if r["tender_title"] == b["tender_title"]), None)
                if scc_match and scc_match["scc_won"]:
                    scc_wins_hth += 1
                elif b["is_won"]:
                    comp_wins_hth += 1
        return {"contests": contests, "scc_wins": scc_wins_hth, f"{competitor_name.lower().split()[0]}_wins": comp_wins_hth}

    for name, meta in profile_meta.items():
        comp = competitor_data.get(name, {})
        overall = overall_stats.get(name, {})
        hth = head_to_head(name, meta["search_keywords"])

        profile = {
            "search_keywords": meta["search_keywords"],
            "total_bids": comp.get("total_bids", 0),
            "wins": comp.get("wins", 0),
            "overall_win_rate": comp.get("win_rate", 0.0),
            "token_bid_rate": comp.get("token_bid_rate", 0.0),
            "genuine_band": meta["genuine_band"],
            "avg_winning_bid_omr": overall.get("avg_winning_bid_omr"),
            "territory": meta.get("territory"),
            "scc_head_to_head": hth,
            "strategic_note": meta["strategic_note"],
        }
        if meta.get("territory") is None:
            del profile["territory"]
        competitor_profiles[name] = profile

    # Al Tasnim special: token rate in 15M-50M band
    at_bids = [b for b in competitor_data.get("Al Tasnim", {}).get("bids", []) if not b["is_won"] and b["gap_pct"] is not None]
    at_15_50 = [b for b in at_bids if b["bid_value"] and 15_000_000 <= float(b["bid_value"]) < 50_000_000]
    at_token_15_50 = sum(1 for b in at_15_50 if b["intent"] == "TOKEN")
    at_token_rate_15_50 = round(at_token_15_50 / len(at_15_50), 3) if at_15_50 else 0.0
    competitor_profiles["Al Tasnim"]["token_bid_rate_15M_50M_band"] = at_token_rate_15_50

    return {
        "metadata": {
            "last_updated": str(date.today()),
            "awarded_tenders_analysed": 4981,
            "scc_bid_appearances": total_scc,
            "scc_wins": scc_wins_total,
            "data_coverage_note": (
                "Covers construction category awarded tenders with bid detail published on "
                "Oman Tender Board. Supply/Services tenders (82.5% of total) excluded as not SCC domain."
            ),
        },
        "scc_performance": {
            "overall_win_rate": overall_win_rate,
            "genuine_competitive_band": genuine_band,
            "genuine_band_win_rate": genuine_band_win_rate,
            "by_size_band": by_size_band,
            "token_bid_rate_overall": scc_token_rate,
            "token_bid_rate_5M_15M_band": scc_token_rate_5_15,
        },
        "scc_entity_performance": {
            k: {
                "bids": v["bids"],
                "wins": v["wins"],
                "win_rate": v["win_rate"],
                "avg_gap_pct": v["avg_gap_pct"],
                "near_misses": v["near_misses"],
                "dominant_rivals": v["dominant_rivals"],
            }
            for k, v in entity_intel.items()
        },
        "scc_near_misses": near_misses[:10],
        "competitor_profiles": competitor_profiles,
        "entity_threat_map": threat_map,
        "scoring_guidance": {
            "score_up_entities": [
                "Muscat Municipality",
                "Ministry of Transport Communications and Information Technology",
                "Ministry of Housing",
            ],
            "score_down_entities": [
                "Ministry of Agricultural, Fisheries Wealth and Water Resources",
                "North Al Batinah Governor Office",
                "South Al Batinah Governor Office",
                "Al Dakhiliyah Governor Office",
                "Office of the Minister of State And Governor of Musandam Governorate",
            ],
            "score_up_categories": [
                "Construction of Ports Roads Bridges Railways Dams and Maintenance",
                "Construction and Maintenance",
            ],
            "score_down_categories": [
                "Supply",
                "Services",
                "Information Technology Services",
            ],
            "doc_purchase_threat_rules": [
                {
                    "competitor": "Al Tasnim",
                    "high_threat_if": "entity in ['North Al Batinah Governor Office', 'Muscat Municipality', 'Al Dakhiliyah Governor Office'] AND estimated_value < 5000000",
                    "low_threat_if": "estimated_value > 15000000",
                    "reason": "Al Tasnim token bid rate 70% above OMR 15M",
                },
                {
                    "competitor": "Galfar",
                    "high_threat_if": "estimated_value > 20000000",
                    "low_threat_if": "estimated_value < 10000000",
                    "reason": "Galfar genuine only at OMR 20M+. 43% token bid rate overall.",
                },
                {
                    "competitor": "Premier International Projects",
                    "high_threat_if": "entity in ['Ministry of Agricultural, Fisheries Wealth and Water Resources', 'Office of the Minister of State And Governor of Musandam Governorate', 'Buraimi Governor Office']",
                    "low_threat_if": "estimated_value > 50000000",
                    "reason": "Premier genuine band is 1M-30M. Specialist in water/dam/agricultural.",
                },
                {
                    "competitor": "Strabag",
                    "high_threat_if": "estimated_value > 15000000",
                    "low_threat_if": "estimated_value < 5000000",
                    "reason": "Strabag most disciplined — when they enter they mean it. 13% token rate.",
                },
            ],
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Build Competitive Intelligence")
    print("=" * 60)

    # Load data
    print("\nLoading awarded_tenders.csv...")
    df = pd.read_csv(AWARDED_CSV)
    print(f"  Loaded {len(df):,} rows")

    # Stage 2 — SCC Bid Extraction
    print("\n[STAGE 2] Extracting SCC bids...")
    scc_bids = extract_scc_bids(df)
    scc_wins = sum(1 for r in scc_bids if r["scc_won"])
    gap_populated = sum(1 for r in scc_bids if r["gap_pct"] is not None)
    rank_populated = sum(1 for r in scc_bids if r["scc_rank"] is not None)
    print(f"  SCC records: {len(scc_bids)} (expected 90)")
    print(f"  Wins: {scc_wins} (expected 7)")
    print(f"  gap_pct populated: {gap_populated}")
    print(f"  scc_rank populated: {rank_populated}")
    with open(SCC_BIDS_JSON, "w") as f:
        json.dump(scc_bids, f, indent=2)
    print(f"  Saved to {SCC_BIDS_JSON}")

    if len(scc_bids) != 90:
        print(f"  WARNING: Expected 90 SCC bids, got {len(scc_bids)}")
    if scc_wins != 7:
        print(f"  WARNING: Expected 7 SCC wins, got {scc_wins}")

    # Stage 3 — Token bid classification
    print("\n[STAGE 3] Classifying competitor bids...")
    competitor_data = classify_all_competitor_bids(df)
    scc_losses = [r for r in scc_bids if not r["scc_won"] and r["gap_pct"] is not None]
    scc_token = sum(1 for r in scc_losses if r["gap_pct"] > 50)
    scc_token_rate = scc_token / len(scc_losses) if scc_losses else 0
    print(f"\n  SCC token rate: {scc_token_rate:.1%} (expected ~33%)")

    scc_5_15 = [r for r in scc_losses if r["scc_bid"] and 5_000_000 <= float(r["scc_bid"]) < 15_000_000]
    scc_token_5_15 = sum(1 for r in scc_5_15 if r["gap_pct"] > 50)
    scc_token_rate_5_15 = scc_token_5_15 / len(scc_5_15) if scc_5_15 else 0
    print(f"  SCC token rate 5M-15M band: {scc_token_rate_5_15:.1%} (expected ~86%)")

    with open(COMPETITOR_BIDS_JSON, "w") as f:
        json.dump(
            {k: {kk: vv for kk, vv in v.items() if kk != "bids"} for k, v in competitor_data.items()},
            f, indent=2
        )
    print(f"  Saved to {COMPETITOR_BIDS_JSON}")

    # Stage 4 — Band analysis
    print("\n[STAGE 4] Analyzing competitor bands...")
    band_analysis = analyze_competitor_bands(competitor_data, scc_bids)
    overall_stats = analyze_competitor_overall(competitor_data)
    for name, ba in band_analysis.items():
        print(f"  {name:40s} genuine_band={ba['genuine_band']}")

    # Stage 5 — Entity intelligence
    print("\n[STAGE 5] Analyzing entity patterns...")
    entity_intel, threat_map = analyze_entity_patterns(scc_bids, competitor_data)
    near_misses = find_near_misses(scc_bids)
    print(f"  Entities with SCC appearances: {len(entity_intel)}")
    print(f"  Near misses (<=10% gap): {len(near_misses)}")
    if near_misses:
        nm = near_misses[0]
        print(f"  Closest near miss: {nm['gap_pct']}% — {nm['entity']}")
    for entity in ["Muscat Municipality",
                   "Ministry of Transport Communications and Information Technology",
                   "Ministry of Agricultural, Fisheries Wealth and Water Resources"]:
        if entity in entity_intel:
            ei = entity_intel[entity]
            print(f"  {entity[:50]:50s}  bids={ei['bids']}  wins={ei['wins']}  win_rate={ei['win_rate']:.1%}")

    # Stage 6 — Assemble JSON
    print("\n[STAGE 6] Assembling competitive_intelligence.json...")
    intel = assemble_intelligence(
        scc_bids, competitor_data, band_analysis, overall_stats,
        entity_intel, threat_map, near_misses
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(intel, f, indent=2)
    size_kb = os.path.getsize(OUTPUT_JSON) / 1024
    print(f"  Saved: {OUTPUT_JSON}")
    print(f"  File size: {size_kb:.1f} KB")

    # Validate top-level keys
    required_keys = ["metadata", "scc_performance", "scc_entity_performance",
                     "scc_near_misses", "competitor_profiles", "entity_threat_map", "scoring_guidance"]
    missing = [k for k in required_keys if k not in intel]
    if missing:
        print(f"  WARNING: Missing keys: {missing}")
    else:
        print(f"  All {len(required_keys)} top-level keys present")

    print(f"  competitor_profiles count: {len(intel['competitor_profiles'])}")
    print(f"  scc_near_misses count: {len(intel['scc_near_misses'])}")
    print(f"  metadata.scc_bid_appearances: {intel['metadata']['scc_bid_appearances']}")

    print("\nDone.")
    return intel, scc_bids, competitor_data, band_analysis, entity_intel, near_misses


if __name__ == "__main__":
    main()
