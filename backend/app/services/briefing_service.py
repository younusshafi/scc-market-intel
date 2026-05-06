"""
Briefing generation service.
Ported from briefing_test.py — builds context from database, calls LLM, stores result.
"""

import re
import logging
from datetime import datetime, timedelta
from collections import defaultdict

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import get_settings
from app.services.llm_client import call_llm
from app.models import Tender, NewsArticle, Briefing, TenderProbe, TenderScore

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = (
    "You are the Head of Competitive Intelligence at Sarooj Construction Company (SCC), "
    "an Omani Tier-1 civil infrastructure contractor. Write a weekly intelligence briefing "
    "in EXACTLY 5 sections with the headers shown. Each section must cite specific tender "
    "numbers, company names, or OMR values — no generic statements. If data is insufficient "
    "for a section, say so explicitly (e.g. 'No qualifying tenders this week') rather than "
    "filling space with vague observations.\n\n"
    "## BID NOW\n"
    "2-3 specific open tenders SCC should prioritize this week. For each: name the tender, "
    "state closing date, cite the AI score, name any tracked competitors already in, and give "
    "one concrete action (e.g. 'submit by Thursday', 'request clarification on scope'). "
    "Prioritise tenders closing within 14 days with score >= 80.\n\n"
    "## WATCH\n"
    "1-2 tenders where key competitors recently purchased documents — a forward signal that "
    "a bid is coming. Name the competitor, name the tender, state when docs were purchased. "
    "Recommend whether SCC should also purchase docs.\n\n"
    "## COMPETITOR ALERT\n"
    "The single most significant competitor move in the last 7 days: contract win, new market "
    "entry, unusual bid pattern, or sharp increase in doc purchases. Name the company and "
    "the tender or contract. If Galfar's order backlog or financials changed, note it.\n\n"
    "## MARKET PULSE\n"
    "One trend in the Oman tender market this month: volume up/down vs last month, a new "
    "issuing entity becoming active, a category seeing more re-tenders than normal. Back it "
    "with numbers from the context.\n\n"
    "## STRATEGIC NOTE\n"
    "One medium-term observation SCC should act on over the next 30-60 days: an entity SCC "
    "should target more, a category where SCC's win rate is below market average, or an "
    "upcoming major project entering procurement. Reference SCC's historical win rate data.\n\n"
    "BANNED PHRASES: 'could lead to', 'may have implications', 'continue monitoring', "
    "'actively pursue', 'indicates potential', 'suggests a need to explore', "
    "any sentence without a specific project/company/number.\n\n"
    "FORMAT: 5 sections with ## headers, prose under each. Max 350 words total. "
    "Write like a strategist to a peer, not an AI report."
)

MAX_CONTEXT_WORDS = 3200

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


def _resolve_comp(name: str) -> str | None:
    """Resolve company name to tracked competitor short name."""
    if name in TRACKED_ALIASES:
        return TRACKED_ALIASES[name]
    low = name.lower()
    for comp in settings.scc_competitors + ["Sarooj"]:
        if comp.lower() in low:
            return comp
    return None


def build_competitive_intel_context(db: Session) -> str:
    """Build competitive intelligence context from TenderProbe data for the LLM."""
    probes = db.query(TenderProbe).all()
    if not probes:
        return ""

    lines = ["=== COMPETITIVE INTELLIGENCE ==="]

    # Find Sarooj's bids and head-to-head
    for probe in probes:
        bidders = probe.bidders or []
        nit = probe.nit or {}
        sarooj_val = None
        comp_vals = []
        for b in bidders:
            rn = _resolve_comp(b.get("company", ""))
            val_str = b.get("quoted_value", "")
            try:
                val = float(val_str) if val_str else 0
            except (ValueError, TypeError):
                val = 0
            if rn == "Sarooj" and val > 0:
                sarooj_val = val
            elif rn and rn != "Sarooj" and val > 0:
                comp_vals.append((rn, val))

        if sarooj_val:
            title = nit.get("title", "") or probe.tender_name or ""
            lines.append(f"\nSCC BID: {title}")
            lines.append(f"  Sarooj bid: OMR {sarooj_val:,.3f}")
            for cn, cv in sorted(comp_vals, key=lambda x: x[1]):
                diff_pct = round((cv - sarooj_val) / sarooj_val * 100, 1)
                lines.append(f"  {cn}: OMR {cv:,.3f} ({'+' if diff_pct >= 0 else ''}{diff_pct}% vs SCC)")

    # Find tenders with many tracked competitors
    lines.append("\nMULTI-COMPETITOR TENDERS:")
    for probe in probes:
        purchasers = probe.purchasers or []
        nit = probe.nit or {}
        tracked = set()
        for p in purchasers:
            rn = _resolve_comp(p.get("company", ""))
            if rn:
                tracked.add(rn)
        if len(tracked) >= 3:
            title = nit.get("title", "") or probe.tender_name or ""
            lines.append(f"  {title}: {len(tracked)} tracked competitors ({', '.join(sorted(tracked))}), {len(purchasers)} total purchasers")

    # Largest competitor bids
    lines.append("\nLARGEST COMPETITOR BIDS:")
    big_bids = []
    for probe in probes:
        for b in (probe.bidders or []):
            rn = _resolve_comp(b.get("company", ""))
            val_str = b.get("quoted_value", "")
            try:
                val = float(val_str) if val_str else 0
            except (ValueError, TypeError):
                val = 0
            if rn and val > 5_000_000:
                nit = probe.nit or {}
                big_bids.append((rn, val, nit.get("title", "") or probe.tender_name or ""))
    big_bids.sort(key=lambda x: -x[1])
    for cn, cv, title in big_bids[:8]:
        lines.append(f"  {cn}: OMR {cv:,.3f} on {title[:60]}")

    return "\n".join(lines)


def build_trend_direction(db: Session) -> str:
    """Build trend direction labels from monthly tender data."""
    tenders = db.query(Tender).all()
    if not tenders:
        return ""

    by_month = defaultdict(int)
    scc_by_month = defaultdict(int)
    rt_by_month = defaultdict(int)
    entity_counts = defaultdict(int)
    retenders = []

    for t in tenders:
        # Extract year-month from bid_closing_date or first_seen
        d = t.bid_closing_date or (t.first_seen.date() if t.first_seen else None)
        if not d:
            continue
        key = f"{d.year}-{d.month:02d}"
        by_month[key] += 1

        if t.is_scc_relevant:
            scc_by_month[key] += 1
            entity = t.entity_en or t.entity_ar or "Unknown"
            entity_counts[entity] += 1

        if t.is_retender:
            retenders.append(t)
            rt_by_month[key] += 1

    all_months = sorted(by_month.keys())
    if not all_months:
        return ""

    recent_months = all_months[-6:] if len(all_months) >= 6 else all_months

    lines = []
    lines.append(f"=== HISTORICAL TRENDS ===")
    lines.append(f"Data spans {all_months[0]} to {all_months[-1]} ({len(all_months)} months, {len(tenders)} tenders)")

    lines.append("\nMonthly tender volume (last 6 months):")
    for m in recent_months:
        scc = scc_by_month.get(m, 0)
        rt = rt_by_month.get(m, 0)
        pct_scc = round(scc / max(by_month[m], 1) * 100, 1)
        rt_str = f", re-tenders: {rt}" if rt else ""
        lines.append(f"  {m}: {by_month[m]:>5} total, {scc:>4} SCC-relevant ({pct_scc}%){rt_str}")

    # SCC-relevant trend direction
    if len(recent_months) >= 2:
        first_half = sum(scc_by_month.get(m, 0) for m in recent_months[:3])
        second_half = sum(scc_by_month.get(m, 0) for m in recent_months[3:])
        if second_half > first_half:
            lines.append(f"  Trend: SCC-relevant tenders INCREASING ({first_half} -> {second_half} in last 3 vs prior 3 months)")
        elif second_half < first_half:
            lines.append(f"  Trend: SCC-relevant tenders DECREASING ({first_half} -> {second_half} in last 3 vs prior 3 months)")
        else:
            lines.append(f"  Trend: SCC-relevant tenders FLAT ({first_half} = {second_half})")

    # Top issuing entities for SCC categories
    lines.append("\nTop entities issuing SCC-relevant tenders:")
    for entity, count in sorted(entity_counts.items(), key=lambda x: -x[1])[:10]:
        lines.append(f"  {entity[:50]}: {count}")

    # Re-tender summary
    lines.append(f"\nRe-tenders total: {len(retenders)}")
    for t in retenders[:5]:
        name = t.tender_name_en or t.tender_name_ar or "?"
        cat = t.category_en or t.category_ar or ""
        lines.append(f"  {t.tender_number} — {name[:50]} ({cat[:40]})")

    return "\n".join(lines)


def build_context_from_db(db: Session) -> str:
    """Build the LLM context payload from database records."""
    sections = []

    # SCC profile
    sections.append(
        "=== SCC COMPANY PROFILE ===\n"
        f"Work categories: roads, bridges, tunnels, marine works, civil infrastructure, dams, pipelines\n"
        f"Eligible grades: Excellent, First, Second\n"
        f"Tracked competitors: {', '.join(settings.scc_competitors)}"
    )

    # Current tender statistics
    tenders = db.query(Tender).all()
    total = len(tenders)
    if total == 0:
        sections.append("=== CURRENT TENDER STATISTICS ===\nNo tenders in database yet.")
    else:
        by_category = defaultdict(int)
        by_grade = defaultdict(int)
        scc_count = 0
        retender_count = 0
        retender_cats = defaultdict(int)

        for t in tenders:
            cat = t.category_en or t.category_ar or "Unknown"
            if cat and len(cat) >= 3:
                by_category[cat] += 1
            grade = t.grade_en or t.grade_ar or ""
            if grade and len(grade) >= 3:
                by_grade[grade] += 1
            if t.is_scc_relevant:
                scc_count += 1
            if t.is_retender:
                retender_count += 1
                retender_cats[cat] += 1

        lines = [f"TOTAL TENDERS: {total}"]
        lines.append("\nBy Procurement Category (count / % of total):")
        for cat, count in sorted(by_category.items(), key=lambda x: -x[1]):
            pct = round(count / total * 100, 1)
            lines.append(f"  {cat}: {count} ({pct}%)")

        lines.append(f"\n  SCC CORE CATEGORIES TOTAL: {scc_count} ({round(scc_count / total * 100, 1)}%)")
        lines.append(f"  OTHER CATEGORIES: {total - scc_count} ({round((total - scc_count) / total * 100, 1)}%)")

        lines.append("\nBy Grade:")
        for grade, count in sorted(by_grade.items(), key=lambda x: -x[1]):
            lines.append(f"  {grade}: {count} ({round(count / total * 100, 1)}%)")

        lines.append(f"\n=== RE-TENDER ANALYSIS ===")
        lines.append(f"Total re-tenders: {retender_count} ({round(retender_count / total * 100, 1)}%)")
        if retender_cats:
            lines.append("Re-tenders by category:")
            for cat, count in sorted(retender_cats.items(), key=lambda x: -x[1]):
                lines.append(f"  {cat}: {count}")

        sections.append("=== CURRENT TENDER STATISTICS ===\n" + "\n".join(lines))

    # SCC-relevant tenders detail
    scc_tenders = db.query(Tender).filter(Tender.is_scc_relevant == True).limit(15).all()
    if scc_tenders:
        lines = [f"=== SCC-RELEVANT TENDERS ({len(scc_tenders)} shown) ==="]
        for t in scc_tenders:
            name = t.tender_name_en or t.tender_name_ar or "?"
            entity = t.entity_en or t.entity_ar or ""
            cat = t.category_en or t.category_ar or ""
            close = t.bid_closing_date.strftime("%d-%m-%Y") if t.bid_closing_date else ""
            lines.append(f"{t.tender_number} | {name[:60]} | {entity[:30]} | {cat[:30]} | {close}")
        sections.append("\n".join(lines))

    # Field definitions
    sections.append(
        "=== FIELD DEFINITIONS ===\n"
        "- Fee: Tender DOCUMENT PURCHASE fee, NOT project value.\n"
        "- Guarantee: Bank guarantee PERCENTAGE, not absolute amount.\n"
        "- Do not comment on fees or guarantees as indicators of project size."
    )

    # Recent news
    cutoff = datetime.utcnow() - timedelta(days=7)
    recent_news = (
        db.query(NewsArticle)
        .filter(NewsArticle.is_relevant == True)
        .filter(NewsArticle.published >= cutoff)
        .order_by(desc(NewsArticle.published))
        .limit(30)
        .all()
    )

    comp_news = [a for a in recent_news if a.is_competitor_mention]
    gen_news = [a for a in recent_news if not a.is_competitor_mention]

    news_lines = []
    if comp_news:
        news_lines.append(f"=== COMPETITOR NEWS ({len(comp_news)} articles) ===")
        for a in comp_news[:10]:
            pub = a.published.strftime("%Y-%m-%d") if a.published else ""
            news_lines.append(f"{a.title} | {a.source} | {pub}")

    if gen_news:
        news_lines.append(f"\n=== GENERAL MARKET NEWS ({len(gen_news)} articles) ===")
        for a in gen_news[:15]:
            pub = a.published.strftime("%Y-%m-%d") if a.published else ""
            summary = (a.summary or "")[:150]
            news_lines.append(f"{a.title} | {a.source} | {pub} | {summary}")

    if news_lines:
        sections.append("\n".join(news_lines))

    # Historical trend direction
    trend_ctx = build_trend_direction(db)
    if trend_ctx:
        sections.append(trend_ctx)

    # Competitive intelligence from probe data
    comp_intel_ctx = build_competitive_intel_context(db)
    if comp_intel_ctx:
        sections.append(comp_intel_ctx)

    # AI-scored top opportunities
    from app.models import TenderScore
    scored = (
        db.query(Tender, TenderScore)
        .join(TenderScore, Tender.tender_number == TenderScore.tender_number)
        .filter(TenderScore.score >= 70)
        .order_by(desc(TenderScore.score))
        .limit(15)
        .all()
    )
    if scored:
        lines = ["=== AI-SCORED TOP OPPORTUNITIES ===",
                 "These tenders have been scored by AI as strong SCC fits:\n"]
        for i, (t, s) in enumerate(scored, 1):
            name = t.tender_name_en or t.tender_name_ar or "?"
            entity = t.entity_en or t.entity_ar or ""
            # Get competitor info from probe
            probe = db.query(TenderProbe).filter_by(tender_number=t.tender_number).first()
            comp_info = ""
            if probe and probe.bidders:
                from app.services.competitive_intel_service import resolve_competitor
                tracked = [resolve_competitor(b.get("company","")) for b in probe.bidders]
                tracked = [c for c in tracked if c]
                if tracked:
                    comp_info = f" — {len(tracked)} tracked competitors: {', '.join(set(tracked))}"
                else:
                    comp_info = " — No tracked competitors"
            lines.append(f"{i}. [Score {s.score}] {name[:60]} — {entity[:40]} — Fee: {t.fee or '?'} OMR — {s.recommendation}{comp_info}")
            if s.reasoning:
                lines.append(f"   Reasoning: {s.reasoning[:80]}")
        sections.append("\n".join(lines))

    # Awarded tender context
    from app.models import AwardedTender
    awarded_construction = db.query(AwardedTender).filter(
        AwardedTender.is_construction == True,
        AwardedTender.winner_company != None
    ).all()

    if awarded_construction:
        award_lines = ["=== HISTORICAL AWARD INTELLIGENCE ==="]

        # Competitor win counts
        from collections import Counter as _Counter
        winner_counts = _Counter()
        for a in awarded_construction:
            if a.winner_company:
                resolved = _resolve_comp(a.winner_company)
                if resolved:
                    winner_counts[resolved] += 1

        if winner_counts:
            award_lines.append("Tracked competitor wins (construction, all time):")
            for comp, count in winner_counts.most_common(8):
                award_lines.append(f"  {comp}: {count} wins")

        # Recent awards in SCC categories
        recent = [a for a in awarded_construction if a.winning_value and a.winning_value > 100000]
        recent.sort(key=lambda x: x.awarded_date or "", reverse=True)
        if recent[:5]:
            award_lines.append("\nRecent major construction awards:")
            for a in recent[:5]:
                award_lines.append(
                    f"  {(a.tender_title or '')[:50]} | Winner: {a.winner_company} "
                    f"| OMR {a.winning_value:,.0f} | {(a.entity or '')[:30]}"
                )

        sections.append("\n".join(award_lines))

    # SCC win rate this year vs last year
    from datetime import date as _date
    _this_year = _date.today().year
    _last_year = _this_year - 1
    scc_ytd = [a for a in awarded_construction if a.winner_company and "sarooj" in a.winner_company.lower()
               and a.awarded_date and a.awarded_date[:4] == str(_this_year)]
    scc_last = [a for a in awarded_construction if a.winner_company and "sarooj" in a.winner_company.lower()
                and a.awarded_date and a.awarded_date[:4] == str(_last_year)]
    total_ytd = [a for a in awarded_construction if a.awarded_date and a.awarded_date[:4] == str(_this_year)]
    total_last = [a for a in awarded_construction if a.awarded_date and a.awarded_date[:4] == str(_last_year)]
    wr_ytd = round(len(scc_ytd)/len(total_ytd)*100,1) if total_ytd else None
    wr_last = round(len(scc_last)/len(total_last)*100,1) if total_last else None

    # Competitor SCC loses to most
    from collections import Counter as _Ctr
    lost_to = _Ctr()
    for a in awarded_construction:
        if a.winner_company and "sarooj" not in a.winner_company.lower():
            resolved = _resolve_comp(a.winner_company)
            if resolved:
                # Check if Sarooj appeared as runner-up (via bidders_json)
                if a.bidders_json:
                    import json as _json
                    try:
                        bids = _json.loads(a.bidders_json)
                        if any("sarooj" in str(b.get("company","")).lower() for b in bids if isinstance(b, dict)):
                            lost_to[resolved] += 1
                    except Exception:
                        pass
    main_rival = lost_to.most_common(1)

    # Competitor activity last 60 days
    cutoff_60 = (datetime.utcnow() - timedelta(days=60)).date().isoformat()
    recent_activity = defaultdict(int)
    all_probes = db.query(TenderProbe).all()
    for probe in all_probes:
        for p in (probe.purchasers or []):
            pd = p.get("purchase_date", "")
            if pd and pd >= cutoff_60:
                rn = _resolve_comp(p.get("company", ""))
                if rn and rn != "Sarooj":
                    recent_activity[rn] += 1

    perf_lines = ["=== SCC PERFORMANCE METRICS ==="]
    if wr_ytd is not None:
        perf_lines.append(f"SCC win rate {_this_year} YTD: {wr_ytd}% ({len(scc_ytd)} wins / {len(total_ytd)} awards)")
    if wr_last is not None:
        perf_lines.append(f"SCC win rate {_last_year}: {wr_last}% ({len(scc_last)} wins / {len(total_last)} awards)")
    if main_rival:
        perf_lines.append(f"Competitor SCC loses to most: {main_rival[0][0]} ({main_rival[0][1]} tenders)")
    if recent_activity:
        top_act = sorted(recent_activity.items(), key=lambda x: -x[1])[:3]
        perf_lines.append(f"Most active competitors (last 60 days doc purchases): {', '.join(f'{c} ({n})' for c, n in top_act)}")
    sections.append("\n".join(perf_lines))

    context = "\n\n".join(sections)

    # Enforce word budget
    word_count = len(context.split())
    if word_count > MAX_CONTEXT_WORDS:
        words = context.split()
        context = " ".join(words[:MAX_CONTEXT_WORDS])
        logger.warning(f"Context truncated from {word_count} to {MAX_CONTEXT_WORDS} words")
        word_count = MAX_CONTEXT_WORDS

    logger.info(f"Context built: {word_count} words, {len(context)} chars")
    return context



def md_to_html(md: str) -> str:
    """Simple markdown to HTML converter for briefings."""
    if not md:
        return "<p><em>No briefing available.</em></p>"
    lines = md.split("\n")
    out = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        if s.startswith("## "):
            out.append(f"<h3>{_inline(s[3:])}</h3>")
        elif s.startswith("# "):
            out.append(f"<h2>{_inline(s[2:])}</h2>")
        elif s.startswith(("* ", "- ")):
            content = re.sub(r"^[\t ]*[*\-]\s+", "", s)
            out.append(f"<li>{_inline(content)}</li>")
        else:
            out.append(f"<p>{_inline(s)}</p>")
    return "\n".join(out)


def _inline(t: str) -> str:
    import html
    t = html.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"\*(.+?)\*", r"<em>\1</em>", t)
    return t


def generate_and_store_briefing(db: Session) -> Briefing | None:
    """Full pipeline: build context → call LLM → store briefing."""
    context = build_context_from_db(db)
    result = call_llm(system_prompt=SYSTEM_PROMPT, user_content=context)

    if not result:
        logger.error("Failed to generate briefing")
        return None

    briefing = Briefing(
        content_md=result["text"],
        content_html=md_to_html(result["text"]),
        context_summary=f"{len(context.split())} words context",
        model_used="gpt-4o-mini",
        token_usage=result["usage"],
    )
    db.add(briefing)
    db.commit()
    db.refresh(briefing)

    logger.info(f"Briefing stored: id={briefing.id}")
    return briefing
