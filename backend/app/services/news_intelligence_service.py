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
    "(SCC), a major Omani civil infrastructure contractor specialising in roads, "
    "bridges, tunnels, marine works, dams, and pipelines.\n\n"
    "You will receive a JSON array of news articles. For each article, produce a "
    "JSON object with:\n"
    "- article_id: the article ID (integer)\n"
    "- relevant: boolean - is this article relevant to SCC's business?\n"
    "- scc_implication: 1-2 sentence explanation of what this means for SCC\n"
    "- category: one of 'COMPETITOR', 'PROJECT', 'POLICY', 'MARKET', 'TECHNOLOGY', 'OTHER'\n"
    "- priority: one of 'HIGH', 'MEDIUM', 'LOW'\n\n"
    "PRIORITY CRITERIA:\n"
    "HIGH: Direct competitor activity (new contracts, JVs, financial issues), "
    "major government infrastructure spending announcements, policy changes "
    "affecting construction sector, new projects SCC could bid on.\n"
    "MEDIUM: Regional market trends, supply chain developments, regulatory "
    "updates, competitor leadership changes.\n"
    "LOW: General economic news, tangentially related industry updates, "
    "international news with limited Oman impact.\n\n"
    "CATEGORY DEFINITIONS:\n"
    "COMPETITOR: News about Galfar, Strabag, Al Tasnim, L&T, Towell, Hassan "
    "Allam, Arab Contractors, Ozkar, or other construction firms active in Oman.\n"
    "PROJECT: New infrastructure projects, contract awards, project completions.\n"
    "POLICY: Government policy, regulations, budget announcements affecting "
    "construction.\n"
    "MARKET: Economic indicators, market trends, investment flows.\n"
    "TECHNOLOGY: Construction technology, innovation, new methods.\n"
    "OTHER: Anything that doesn't fit the above categories.\n\n"
    "Return a JSON object with key 'analyses' containing an array of analysis "
    "objects.\n"
    "Example: {\"analyses\": [{\"article_id\": 1, \"relevant\": true, "
    "\"scc_implication\": \"Galfar winning this contract...\", "
    "\"category\": \"COMPETITOR\", \"priority\": \"HIGH\"}]}"
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
