"""
News intelligence analysis service.
Uses Groq LLM to analyse news articles for SCC strategic implications.
"""

import json
import re
import time
import logging
from datetime import datetime, timedelta

import requests
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import get_settings
from app.models import NewsArticle, NewsIntelligence

logger = logging.getLogger(__name__)

NEWS_ANALYSIS_SYSTEM_PROMPT = (
    "You are a strategic intelligence analyst for Sarooj Construction Company "
    "(SCC), a major Omani Tier-1 civil infrastructure contractor specialising in "
    "roads, highways, bridges, tunnels, marine works, dams, and pipelines. "
    "SCC holds Excellent and First grade classifications.\n\n"
    "You will receive a JSON array of news articles. For each article, produce a "
    "JSON object with:\n"
    "- article_id: the article ID (integer)\n"
    "- relevant: boolean - is this directly relevant to construction/infrastructure?\n"
    "- scc_implication: 1-2 SPECIFIC sentences (see rules below)\n"
    "- category: one of 'COMPETITOR', 'PROJECT', 'POLICY', 'MARKET', 'OTHER'\n"
    "- priority: one of 'HIGH', 'MEDIUM', 'LOW'\n\n"
    "PRIORITY CRITERIA (STRICT):\n"
    "HIGH: Article names a SPECIFIC construction project, contract award value, "
    "or reports tracked competitor winning/losing a bid. Example: 'Strabag wins "
    "$117M Oman road project' = HIGH.\n"
    "MEDIUM: Article discusses infrastructure spending with specific values or "
    "geography, development zone expansion, or industrial/port development that "
    "will require civil works. Example: 'Palm Hills financing deals in Musandam' "
    "= MEDIUM (signals future civil works).\n"
    "LOW: General economic/trade context, policy meetings, trade agreements, "
    "general GCC cooperation — things that MIGHT lead to construction spending "
    "but don't name specific projects or values.\n\n"
    "NOT RELEVANT (relevant=false): Sports, culture, diplomacy meetings, "
    "wildlife, education policy, health campaigns, livestock/agriculture "
    "(unless it involves construction of facilities), military, general "
    "politics, GCC trade meetings, PPP projects for non-construction sectors "
    "(biosecurity, livestock, fisheries management).\n\n"
    "CRITICAL RULES FOR SCC IMPLICATIONS:\n"
    "- NEVER use phrases like 'could lead to new business opportunities' "
    "or 'could be a potential bid opportunity' — these are USELESS\n"
    "- Every implication MUST name at least ONE of: specific construction "
    "type, specific governorate, specific competitor, specific timeline, "
    "or specific OMR value\n"
    "- If you cannot write a specific implication, set relevant=false\n"
    "- ALWAYS name the specific type of construction work (road construction, "
    "bridge building, port development, pipeline laying, earthworks)\n"
    "- ALWAYS reference the geography if mentioned (governorate, wilayat, city)\n"
    "- If a tracked competitor is named, mention them and what it means for SCC\n"
    "- Give a concrete timeline if inferable ('tenders likely in 6-12 months')\n"
    "- If the article mentions a project value, reference it\n"
    "- If the connection to SCC is weak, write 'Low direct relevance to SCC "
    "civil infrastructure work' instead of inventing a vague connection\n\n"
    "BAD (NEVER write these):\n"
    "- 'Could lead to new business opportunities for SCC'\n"
    "- 'This could be a potential bid opportunity'\n"
    "- 'May create future construction opportunities'\n"
    "- 'SCC should monitor developments'\n\n"
    "GOOD (write like these):\n"
    "- 'Pipeline tenders in Al Batinah likely within 6-12 months. "
    "Monitor Nama procurement for civil works packages.'\n"
    "- 'Road and site preparation works for Duqm steel plant. "
    "OMR 3,000+ fee bracket. No tracked competitors yet — early "
    "positioning advantage.'\n"
    "- 'Strabag EUR 102M Oman road contract on Sohar-Buraimi axis "
    "directly competes with SCC. Monitor MTCIT tenders for related "
    "package work.'\n\n"
    "Tracked competitors: Galfar, Strabag, Al Tasnim, L&T, Towell, "
    "Hassan Allam, Arab Contractors, Ozkar\n\n"
    "FEW-SHOT EXAMPLES (match this quality exactly):\n\n"
    "Example 1 (HIGH priority):\n"
    "Article: 'Strabag wins $117m Oman road project - MEED'\n"
    "Output: {\"article_id\": 99, \"relevant\": true, "
    "\"scc_implication\": \"Strabag awarded $117M (approx OMR 45M) road "
    "modernisation contract on a major Oman transport axis. This is direct "
    "competition in SCC's core roads category. Check if sub-contract or "
    "adjacent package tenders follow on the Tender Board.\", "
    "\"category\": \"COMPETITOR\", \"priority\": \"HIGH\"}\n\n"
    "Example 2 (MEDIUM priority):\n"
    "Article: 'Port of Duqm joins Oman Net Zero Centre Meezan platform'\n"
    "Output: {\"article_id\": 42, \"relevant\": true, "
    "\"scc_implication\": \"Duqm port sustainability investment signals future "
    "civil works for green infrastructure — hydrogen facilities, carbon "
    "capture structures. Al Wusta governorate. Tenders likely 12-18 months "
    "out via SEZAD procurement.\", "
    "\"category\": \"PROJECT\", \"priority\": \"MEDIUM\"}\n\n"
    "Example 3 (LOW / not relevant):\n"
    "Article: 'Oman participates in GCC meeting on trade'\n"
    "Output: {\"article_id\": 7, \"relevant\": false, "
    "\"scc_implication\": null, \"category\": null, \"priority\": null}\n\n"
    "Return a JSON object with key 'analyses' containing an array.\n"
)


def _call_groq_json(system_prompt: str, user_content: str) -> dict | list | None:
    """Call Groq API expecting JSON response."""
    settings = get_settings()
    if not settings.groq_api_key:
        logger.error("GROQ_API_KEY not set")
        return None

    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
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

    logger.info("Calling Groq API for news analysis...")
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=90,
        )
    except requests.RequestException as e:
        logger.error(f"Groq API request failed: {e}")
        return None

    if r.status_code != 200:
        logger.error(f"Groq API returned {r.status_code}: {r.text[:300]}")
        return None

    text = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\[.*\]', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        logger.error(f"Failed to parse JSON from Groq: {text[:200]}")
        return None


def analyse_news(db: Session) -> dict:
    """Analyse recent news articles for SCC strategic implications."""
    # Get articles from last 7 days that are relevant
    cutoff = datetime.utcnow() - timedelta(days=7)
    recent_articles = (
        db.query(NewsArticle)
        .filter(NewsArticle.is_relevant == True)
        .filter(NewsArticle.published >= cutoff)
        .order_by(desc(NewsArticle.published))
        .all()
    )

    if not recent_articles:
        return {"status": "no_articles", "analysed": 0}

    # Skip already-analysed ones
    already_analysed = set(
        r[0] for r in db.query(NewsIntelligence.article_id).all()
    )
    to_analyse = [a for a in recent_articles if a.id not in already_analysed]

    if not to_analyse:
        return {"status": "all_analysed", "analysed": 0, "total_recent": len(recent_articles)}

    # Process in batches of 10
    batch_size = 10
    analysed = 0
    for i in range(0, len(to_analyse), batch_size):
        batch = to_analyse[i:i + batch_size]
        article_descs = []
        for a in batch:
            article_descs.append({
                "article_id": a.id,
                "title": a.title,
                "source": a.source,
                "published": a.published.isoformat() if a.published else None,
                "summary": (a.summary or "")[:500],
                "is_competitor_mention": a.is_competitor_mention,
                "mentioned_competitors": a.mentioned_competitors,
            })

        user_content = json.dumps(article_descs, ensure_ascii=False)
        result = _call_groq_json(NEWS_ANALYSIS_SYSTEM_PROMPT, user_content)

        if result:
            items = result if isinstance(result, list) else result.get("analyses", result.get("articles", [result]))
            for item in items:
                aid = item.get("article_id")
                if not aid:
                    continue
                existing = db.query(NewsIntelligence).filter_by(article_id=aid).first()
                if existing:
                    existing.relevant = item.get("relevant", True)
                    existing.scc_implication = item.get("scc_implication", "")
                    existing.category = item.get("category", "")
                    existing.priority = item.get("priority", "")
                    existing.analysed_at = datetime.utcnow()
                else:
                    db.add(NewsIntelligence(
                        article_id=aid,
                        relevant=item.get("relevant", True),
                        scc_implication=item.get("scc_implication", ""),
                        category=item.get("category", ""),
                        priority=item.get("priority", ""),
                    ))
                analysed += 1
            db.commit()

        if i + batch_size < len(to_analyse):
            time.sleep(2)  # Rate limit

    return {"status": "success", "analysed": analysed, "total_recent": len(recent_articles)}
