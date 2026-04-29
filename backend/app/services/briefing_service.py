"""
Briefing generation service.
Ported from briefing_test.py — builds context from database, calls LLM, stores result.
"""

import re
import logging
from datetime import datetime, timedelta
from collections import defaultdict

import requests
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import get_settings
from app.models import Tender, NewsArticle, Briefing

logger = logging.getLogger(__name__)
settings = get_settings()

SYSTEM_PROMPT = (
    "You are a senior market intelligence analyst embedded in Sarooj "
    "Construction Company's tendering department. SCC is a major Omani civil "
    "infrastructure contractor — core work: roads, bridges, tunnels, marine "
    "works, dams, pipelines. Grades: Excellent and First.\n\n"
    "Write a weekly briefing for the Head of Tendering and CEO. They are "
    "experienced executives who already monitor the portal daily. Do not "
    "tell them what they already know. Tell them what they cannot easily "
    "see themselves.\n\n"
    "MARKET COMPOSITION (1 paragraph):\n"
    "Analyse the tender mix by category. What percentage of active tenders "
    "fall in SCC's core categories vs other categories? What does the "
    "current composition tell us about where government spending is going "
    "right now? Is SCC's addressable market growing or shrinking relative "
    "to total tender volume? Use specific numbers and percentages.\n\n"
    "PIPELINE OUTLOOK (1 paragraph):\n"
    "What tenders in SCC's core categories are worth watching? Filter "
    "ruthlessly — school maintenance and health centre repairs are not "
    "SCC's business even if they technically match a grade. Only highlight "
    "tenders that involve roads, bridges, tunnels, marine, dams, pipelines, "
    "or major civil infrastructure at a scale SCC would realistically bid. "
    "If nothing qualifies, say so clearly in one sentence and pivot to "
    "forward-looking signals.\n\n"
    "RE-TENDER PATTERNS (1 paragraph):\n"
    "How many re-tenders exist in the current data? What categories are "
    "they concentrated in? Analyse what the pattern suggests.\n\n"
    "COMPETITIVE & STRATEGIC SIGNALS (1 paragraph):\n"
    "Any government policy, investment, or infrastructure announcements that "
    "signal future spending in SCC's categories? Connect the dots to SCC's "
    "business specifically. If recommending action, be concrete.\n\n"
    "FORMAT RULES:\n"
    "- 4 paragraphs with bold headers\n"
    "- Every paragraph must contain at least 2 specific numbers or percentages\n"
    "- Total: 300-400 words\n"
    "- Never say 'it is essential to continue monitoring'\n"
    "- Never say 'may have indirect implications'\n"
    "- Write as a strategist, not a reporter"
)

MAX_CONTEXT_WORDS = 3200


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

    context = "\n\n".join(sections)
    word_count = len(context.split())
    logger.info(f"Context built: {word_count} words, {len(context)} chars")
    return context


def call_groq(context: str) -> dict | None:
    """Call Groq API with the context. Returns {text, usage} or None."""
    api_key = settings.groq_api_key
    if not api_key:
        logger.error("GROQ_API_KEY not set")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
        "temperature": 0.4,
        "max_tokens": 2048,
    }

    logger.info("Calling Groq API...")
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
    except requests.RequestException as e:
        logger.error(f"Groq API request failed: {e}")
        return None

    if r.status_code != 200:
        logger.error(f"Groq API returned {r.status_code}: {r.text[:300]}")
        return None

    data = r.json()
    choices = data.get("choices", [])
    if not choices:
        logger.error("No choices in Groq response")
        return None

    text = choices[0].get("message", {}).get("content", "")
    usage = data.get("usage", {})
    logger.info(f"Groq response: {len(text)} chars, tokens={usage}")
    return {"text": text, "usage": usage}


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
    result = call_groq(context)

    if not result:
        logger.error("Failed to generate briefing")
        return None

    briefing = Briefing(
        content_md=result["text"],
        content_html=md_to_html(result["text"]),
        context_summary=f"{len(context.split())} words context",
        model_used="llama-3.3-70b-versatile",
        token_usage=result["usage"],
    )
    db.add(briefing)
    db.commit()
    db.refresh(briefing)

    logger.info(f"Briefing stored: id={briefing.id}")
    return briefing
