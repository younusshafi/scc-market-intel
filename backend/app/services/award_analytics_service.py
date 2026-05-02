"""Award analytics service — pure data computations from awarded tender history."""

import json
import logging
from collections import Counter, defaultdict
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import AwardedTender
from app.services.competitive_intel_service import resolve_competitor, COMPETITORS

logger = logging.getLogger(__name__)

# Cache for computed analytics (in-memory, recomputed on trigger)
_analytics_cache = {"data": None, "computed_at": None}


def _parse_year(awarded_date: str) -> int | None:
    """Extract year from awarded_date string."""
    if not awarded_date:
        return None
    try:
        # Formats: "2024-03-15", "15/03/2024", "2024"
        if "-" in awarded_date:
            return int(awarded_date[:4])
        if "/" in awarded_date:
            parts = awarded_date.split("/")
            # Could be DD/MM/YYYY or MM/DD/YYYY
            for p in parts:
                if len(p) == 4:
                    return int(p)
        if len(awarded_date) == 4:
            return int(awarded_date)
    except (ValueError, IndexError):
        pass
    return None


def _resolve_bidder(company: str) -> str | None:
    """Resolve a bidder company name to tracked competitor."""
    if not company:
        return None
    return resolve_competitor(company)


def compute_award_analytics(db: Session) -> dict:
    """Compute comprehensive analytics from awarded tender data."""
    logger.info("Computing award analytics...")

    # Load all construction tenders with bid details
    all_tenders = db.query(AwardedTender).filter(
        AwardedTender.is_construction == True
    ).all()

    if not all_tenders:
        return {"status": "no_data"}

    # Parse all bidders upfront
    tender_bidders = {}  # internal_id -> list of parsed bidders
    for t in all_tenders:
        if t.bidders_json:
            try:
                bidders = json.loads(t.bidders_json) if isinstance(t.bidders_json, str) else t.bidders_json
                tender_bidders[t.internal_id] = bidders if isinstance(bidders, list) else []
            except (json.JSONDecodeError, TypeError):
                tender_bidders[t.internal_id] = []
        else:
            tender_bidders[t.internal_id] = []

    # === YEARLY TRENDS ===
    yearly_trends = _compute_yearly_trends(all_tenders, tender_bidders)

    # === COMPETITOR DEEP ANALYTICS ===
    competitor_deep = _compute_competitor_deep(all_tenders, tender_bidders)

    # === ENTITY BEHAVIOUR ===
    entity_behaviour = _compute_entity_behaviour(all_tenders, tender_bidders)

    # === PRICING ANALYTICS ===
    pricing = _compute_pricing(all_tenders, tender_bidders)

    # === SCC PERFORMANCE ===
    scc_performance = _compute_scc_performance(all_tenders, tender_bidders)

    result = {
        "yearly_trends": yearly_trends,
        "competitor_deep": competitor_deep,
        "entity_behaviour": entity_behaviour,
        "pricing": pricing,
        "scc_performance": scc_performance,
        "total_tenders_analysed": len(all_tenders),
        "total_with_bidders": sum(1 for v in tender_bidders.values() if v),
    }

    # Cache it
    _analytics_cache["data"] = result
    _analytics_cache["computed_at"] = datetime.utcnow().isoformat()

    logger.info(f"Analytics computed: {len(all_tenders)} tenders, "
                f"{len(yearly_trends)} years, {len(competitor_deep)} competitors")
    return result


def get_cached_analytics() -> dict | None:
    """Return cached analytics if available."""
    if _analytics_cache["data"]:
        return {**_analytics_cache["data"], "computed_at": _analytics_cache["computed_at"]}
    return None


def _compute_yearly_trends(tenders, tender_bidders) -> list:
    """Per-year statistics."""
    year_data = defaultdict(lambda: {
        "total_awards": 0, "total_value": 0, "winning_bids": [],
        "bidder_counts": [], "comp_stats": defaultdict(lambda: {"bids": 0, "wins": 0, "value_won": 0}),
    })

    for t in tenders:
        year = _parse_year(t.awarded_date)
        if not year or year < 2012:
            continue

        yd = year_data[year]
        yd["total_awards"] += 1

        if t.winning_value and t.winning_value > 0:
            yd["total_value"] += t.winning_value
            yd["winning_bids"].append(t.winning_value)

        if t.num_bidders and t.num_bidders > 0:
            yd["bidder_counts"].append(t.num_bidders)

        # Winner
        winner = _resolve_bidder(t.winner_company) if t.winner_company else None
        if winner:
            yd["comp_stats"][winner]["wins"] += 1
            if t.winning_value:
                yd["comp_stats"][winner]["value_won"] += t.winning_value

        # Bidders
        bidders = tender_bidders.get(t.internal_id, [])
        seen = set()
        for b in bidders:
            comp = _resolve_bidder(b.get("company", "") if isinstance(b, dict) else "")
            if comp and comp not in seen:
                seen.add(comp)
                yd["comp_stats"][comp]["bids"] += 1

    # Build sorted result
    result = []
    for year in sorted(year_data.keys()):
        yd = year_data[year]
        wb = yd["winning_bids"]
        bc = yd["bidder_counts"]

        competitors = {}
        for comp, stats in yd["comp_stats"].items():
            bids = stats["bids"]
            wins = stats["wins"]
            competitors[comp] = {
                "bids": bids,
                "wins": wins,
                "win_rate": round((wins / bids) * 100, 1) if bids > 0 else 0,
                "value_won": round(stats["value_won"], 2),
            }

        result.append({
            "year": year,
            "total_awards": yd["total_awards"],
            "total_value": round(yd["total_value"], 2),
            "avg_winning_bid": round(sum(wb) / len(wb), 2) if wb else 0,
            "median_winning_bid": round(sorted(wb)[len(wb) // 2], 2) if wb else 0,
            "avg_bidders": round(sum(bc) / len(bc), 1) if bc else 0,
            "competitors": competitors,
        })

    return result


def _compute_competitor_deep(tenders, tender_bidders) -> dict:
    """Deep analytics per tracked competitor."""
    comp_data = {name: {
        "total_bids": 0, "wins": 0, "winning_values": [],
        "win_positions": [], "entity_wins": Counter(), "category_wins": Counter(),
        "size_bracket_wins": defaultdict(int), "size_bracket_bids": defaultdict(int),
        "yearly_wins": defaultdict(int), "yearly_bids": defaultdict(int),
        "bid_spreads": [],
    } for name in COMPETITORS}

    for t in tenders:
        year = _parse_year(t.awarded_date)
        bidders = tender_bidders.get(t.internal_id, [])
        winner = _resolve_bidder(t.winner_company) if t.winner_company else None

        # Determine size bracket
        val = t.winning_value or 0
        if val < 100000:
            bracket = "<100K"
        elif val < 1000000:
            bracket = "100K-1M"
        elif val < 10000000:
            bracket = "1M-10M"
        else:
            bracket = "10M+"

        # Parse all bid values and sort to find positions
        bid_values = []
        bidder_comps = []
        for b in bidders:
            if not isinstance(b, dict):
                continue
            comp = _resolve_bidder(b.get("company", ""))
            try:
                bval = float(b.get("quoted_value", 0) or 0)
            except (ValueError, TypeError):
                bval = 0
            if bval > 0:
                bid_values.append(bval)
            bidder_comps.append((comp, bval))

        sorted_bids = sorted([v for v in bid_values if v > 0])
        bid_spread = None
        if len(sorted_bids) >= 2:
            bid_spread = round(((sorted_bids[-1] - sorted_bids[0]) / sorted_bids[0]) * 100, 1)

        # Track per-competitor
        seen = set()
        for comp, bval in bidder_comps:
            if not comp or comp in seen:
                continue
            seen.add(comp)

            if comp not in comp_data:
                continue

            cd = comp_data[comp]
            cd["total_bids"] += 1

            if year:
                cd["yearly_bids"][year] += 1

            cd["size_bracket_bids"][bracket] += 1

            if bid_spread is not None:
                cd["bid_spreads"].append(bid_spread)

            # Check if this competitor won
            if comp == winner:
                cd["wins"] += 1
                if t.winning_value:
                    cd["winning_values"].append(t.winning_value)
                if t.entity:
                    cd["entity_wins"][t.entity] += 1
                if t.category:
                    cd["category_wins"][t.category] += 1
                cd["size_bracket_wins"][bracket] += 1
                if year:
                    cd["yearly_wins"][year] += 1

                # Win position (1 = lowest bidder won)
                if bval > 0 and sorted_bids:
                    pos = sorted_bids.index(bval) + 1 if bval in sorted_bids else None
                    if pos:
                        cd["win_positions"].append(pos)

    # Build response
    result = {}
    for comp, cd in comp_data.items():
        if cd["total_bids"] == 0 and cd["wins"] == 0:
            continue

        wins = cd["wins"]
        bids = cd["total_bids"]
        win_rate = round((wins / bids) * 100, 1) if bids > 0 else 0
        avg_win_val = round(sum(cd["winning_values"]) / len(cd["winning_values"]), 2) if cd["winning_values"] else 0
        avg_win_pos = round(sum(cd["win_positions"]) / len(cd["win_positions"]), 1) if cd["win_positions"] else None

        # Top entities
        top_entities = [{"entity": e, "wins": c} for e, c in cd["entity_wins"].most_common(5)]

        # Top categories
        top_categories = [{"category": c, "wins": n} for c, n in cd["category_wins"].most_common(5)]

        # Size bracket performance
        size_brackets = {}
        for bracket in ["<100K", "100K-1M", "1M-10M", "10M+"]:
            b_bids = cd["size_bracket_bids"].get(bracket, 0)
            b_wins = cd["size_bracket_wins"].get(bracket, 0)
            size_brackets[bracket] = {
                "bids": b_bids, "wins": b_wins,
                "win_rate": round((b_wins / b_bids) * 100, 1) if b_bids > 0 else 0,
            }

        # Avg bid spread
        avg_spread = round(sum(cd["bid_spreads"]) / len(cd["bid_spreads"]), 1) if cd["bid_spreads"] else None

        # Trend: win rate last 3 years vs prior
        recent_years = sorted(cd["yearly_bids"].keys())[-3:] if cd["yearly_bids"] else []
        older_years = [y for y in cd["yearly_bids"].keys() if y not in recent_years]
        recent_bids = sum(cd["yearly_bids"][y] for y in recent_years)
        recent_wins = sum(cd["yearly_wins"].get(y, 0) for y in recent_years)
        older_bids = sum(cd["yearly_bids"][y] for y in older_years)
        older_wins = sum(cd["yearly_wins"].get(y, 0) for y in older_years)
        recent_wr = round((recent_wins / recent_bids) * 100, 1) if recent_bids > 0 else 0
        older_wr = round((older_wins / older_bids) * 100, 1) if older_bids > 0 else 0

        if recent_wr > older_wr + 5:
            trend = "increasing"
        elif recent_wr < older_wr - 5:
            trend = "decreasing"
        else:
            trend = "stable"

        result[comp] = {
            "total_bids": bids,
            "wins": wins,
            "win_rate": win_rate,
            "avg_winning_bid": avg_win_val,
            "avg_win_position": avg_win_pos,
            "top_entities": top_entities,
            "top_categories": top_categories,
            "size_brackets": size_brackets,
            "avg_bid_spread": avg_spread,
            "trend": trend,
            "recent_win_rate": recent_wr,
            "historical_win_rate": older_wr,
            "total_value_won": round(sum(cd["winning_values"]), 2),
        }

    return result


def _compute_entity_behaviour(tenders, tender_bidders) -> list:
    """Entity behaviour analytics for top 15 entities."""
    entity_data = defaultdict(lambda: {
        "total_awards": 0, "total_value": 0, "bidder_counts": [],
        "lowest_wins": 0, "total_with_lowest": 0,
        "comp_wins": Counter(), "winning_values": [],
    })

    for t in tenders:
        if not t.entity:
            continue

        ed = entity_data[t.entity]
        ed["total_awards"] += 1

        if t.winning_value and t.winning_value > 0:
            ed["total_value"] += t.winning_value
            ed["winning_values"].append(t.winning_value)

        if t.num_bidders and t.num_bidders > 0:
            ed["bidder_counts"].append(t.num_bidders)

        # Lowest bidder wins check
        if t.lowest_bid and t.winning_value and t.lowest_bid > 0:
            ed["total_with_lowest"] += 1
            if abs(t.winning_value - t.lowest_bid) < 1:
                ed["lowest_wins"] += 1

        # Winner tracking
        winner = _resolve_bidder(t.winner_company) if t.winner_company else None
        if winner:
            ed["comp_wins"][winner] += 1

    # Sort by total construction awards, take top 15
    sorted_entities = sorted(entity_data.items(), key=lambda x: -x[1]["total_awards"])[:15]

    result = []
    for entity, ed in sorted_entities:
        avg_bidders = round(sum(ed["bidder_counts"]) / len(ed["bidder_counts"]), 1) if ed["bidder_counts"] else None
        avg_value = round(ed["total_value"] / ed["total_awards"], 2) if ed["total_awards"] > 0 else 0
        lowest_pct = round((ed["lowest_wins"] / ed["total_with_lowest"]) * 100, 1) if ed["total_with_lowest"] > 0 else None

        top_winners = [{"company": c, "wins": n} for c, n in ed["comp_wins"].most_common(5)]

        result.append({
            "entity": entity,
            "total_awards": ed["total_awards"],
            "total_value": round(ed["total_value"], 2),
            "avg_contract_value": avg_value,
            "avg_bidders": avg_bidders,
            "lowest_bidder_wins_pct": lowest_pct,
            "top_winners": top_winners,
        })

    return result


def _compute_pricing(tenders, tender_bidders) -> dict:
    """Pricing analytics."""
    # Overall lowest bidder wins
    total_with_lowest = 0
    lowest_wins = 0
    all_spreads = []
    category_pricing = defaultdict(lambda: {"values": [], "spreads": []})
    grade_pricing = defaultdict(lambda: {"values": []})

    for t in tenders:
        if t.winning_value and t.winning_value > 0:
            if t.category:
                category_pricing[t.category]["values"].append(t.winning_value)
            if t.grade:
                grade_pricing[t.grade]["values"].append(t.winning_value)

        if t.lowest_bid and t.winning_value and t.lowest_bid > 0:
            total_with_lowest += 1
            if abs(t.winning_value - t.lowest_bid) < 1:
                lowest_wins += 1

        if t.bid_spread_pct is not None:
            all_spreads.append(t.bid_spread_pct)
            if t.category:
                category_pricing[t.category]["spreads"].append(t.bid_spread_pct)

    lowest_wins_pct = round((lowest_wins / total_with_lowest) * 100, 1) if total_with_lowest > 0 else None
    avg_spread = round(sum(all_spreads) / len(all_spreads), 1) if all_spreads else None

    # By category (top 10 by sample size)
    by_category = []
    for cat, data in sorted(category_pricing.items(), key=lambda x: -len(x[1]["values"]))[:10]:
        vals = data["values"]
        spreads = data["spreads"]
        sorted_vals = sorted(vals)
        by_category.append({
            "category": cat,
            "sample_size": len(vals),
            "avg_winning_bid": round(sum(vals) / len(vals), 2) if vals else 0,
            "median_winning_bid": round(sorted_vals[len(sorted_vals) // 2], 2) if sorted_vals else 0,
            "avg_spread": round(sum(spreads) / len(spreads), 1) if spreads else None,
        })

    # By grade
    by_grade = []
    for grade, data in grade_pricing.items():
        vals = data["values"]
        if len(vals) < 5:
            continue
        by_grade.append({
            "grade": grade,
            "sample_size": len(vals),
            "avg_winning_bid": round(sum(vals) / len(vals), 2),
        })

    return {
        "lowest_bidder_wins_pct": lowest_wins_pct,
        "avg_bid_spread_pct": avg_spread,
        "sample_size": total_with_lowest,
        "by_category": by_category,
        "by_grade": by_grade,
    }


def _compute_scc_performance(tenders, tender_bidders) -> dict:
    """SCC-specific performance analytics."""
    scc_bids = 0
    scc_wins = 0
    scc_win_values = []
    scc_bid_values = []
    scc_positions = []  # position among all bidders (1 = lowest)
    scc_vs_winner = []  # gap between SCC bid and winning bid
    scc_lost_to = Counter()
    scc_win_entities = Counter()
    scc_loss_entities = Counter()
    scc_win_categories = Counter()
    scc_loss_categories = Counter()
    scc_yearly = defaultdict(lambda: {"bids": 0, "wins": 0, "value_won": 0})
    scc_lowest_bidder_count = 0
    scc_lowest_bidder_wins = 0

    for t in tenders:
        bidders = tender_bidders.get(t.internal_id, [])
        if not bidders:
            continue

        year = _parse_year(t.awarded_date)
        winner = _resolve_bidder(t.winner_company) if t.winner_company else None

        # Find SCC in bidders
        scc_val = None
        all_vals = []
        for b in bidders:
            if not isinstance(b, dict):
                continue
            comp = _resolve_bidder(b.get("company", ""))
            try:
                val = float(b.get("quoted_value", 0) or 0)
            except (ValueError, TypeError):
                val = 0
            if val > 0:
                all_vals.append(val)
            if comp == "Sarooj" and val > 0:
                scc_val = val

        if scc_val is None:
            continue

        # SCC participated in this tender
        scc_bids += 1
        scc_bid_values.append(scc_val)

        if year:
            scc_yearly[year]["bids"] += 1

        # Position
        sorted_vals = sorted(all_vals)
        if scc_val in sorted_vals:
            pos = sorted_vals.index(scc_val) + 1
            scc_positions.append(pos)

            # Was SCC lowest bidder?
            if pos == 1:
                scc_lowest_bidder_count += 1

        # Did SCC win?
        if winner == "Sarooj":
            scc_wins += 1
            if t.winning_value:
                scc_win_values.append(t.winning_value)
            if t.entity:
                scc_win_entities[t.entity] += 1
            if t.category:
                scc_win_categories[t.category] += 1
            if year:
                scc_yearly[year]["wins"] += 1
                if t.winning_value:
                    scc_yearly[year]["value_won"] += t.winning_value
            if pos == 1:
                scc_lowest_bidder_wins += 1
        else:
            # SCC lost
            if winner:
                scc_lost_to[winner] += 1
            if t.entity:
                scc_loss_entities[t.entity] += 1
            if t.category:
                scc_loss_categories[t.category] += 1

            # Gap to winner
            if t.winning_value and t.winning_value > 0:
                gap = scc_val - t.winning_value
                gap_pct = round((gap / t.winning_value) * 100, 1)
                scc_vs_winner.append(gap_pct)

    # Build yearly trend
    yearly = []
    for year in sorted(scc_yearly.keys()):
        yd = scc_yearly[year]
        yearly.append({
            "year": year,
            "bids": yd["bids"],
            "wins": yd["wins"],
            "win_rate": round((yd["wins"] / yd["bids"]) * 100, 1) if yd["bids"] > 0 else 0,
            "value_won": round(yd["value_won"], 2),
        })

    win_rate = round((scc_wins / scc_bids) * 100, 1) if scc_bids > 0 else 0
    avg_position = round(sum(scc_positions) / len(scc_positions), 1) if scc_positions else None
    avg_gap_to_winner = round(sum(scc_vs_winner) / len(scc_vs_winner), 1) if scc_vs_winner else None
    lowest_bidder_win_rate = round((scc_lowest_bidder_wins / scc_lowest_bidder_count) * 100, 1) if scc_lowest_bidder_count > 0 else None

    return {
        "total_bids": scc_bids,
        "total_wins": scc_wins,
        "win_rate": win_rate,
        "total_value_won": round(sum(scc_win_values), 2),
        "avg_winning_bid": round(sum(scc_win_values) / len(scc_win_values), 2) if scc_win_values else 0,
        "avg_bid_position": avg_position,
        "avg_gap_to_winner_pct": avg_gap_to_winner,
        "lowest_bidder_count": scc_lowest_bidder_count,
        "lowest_bidder_win_rate": lowest_bidder_win_rate,
        "lost_to": [{"company": c, "count": n} for c, n in scc_lost_to.most_common(10)],
        "win_entities": [{"entity": e, "wins": n} for e, n in scc_win_entities.most_common(5)],
        "loss_entities": [{"entity": e, "losses": n} for e, n in scc_loss_entities.most_common(5)],
        "win_categories": [{"category": c, "wins": n} for c, n in scc_win_categories.most_common(5)],
        "loss_categories": [{"category": c, "losses": n} for c, n in scc_loss_categories.most_common(5)],
        "yearly": yearly,
    }
