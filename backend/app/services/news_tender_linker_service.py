"""News-to-tender linker service — connects news signals to active tenders."""
import json, logging, re
from datetime import datetime

import requests
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import NewsArticle, NewsIntelligence, Tender, NewsTenderLink

logger = logging.getLogger(__name__)

LINKER_SYSTEM_PROMPT = """You are a market intelligence analyst for Sarooj Construction Company (SCC). A news article mentions a project or spending announcement. I've found potentially matching tenders on the Oman Tender Board portal.

For each news-tender pair, assess:
- match_confidence: "confirmed" (same project), "likely" (same entity + category), "possible" (same geography/sector)
- connection: 1 sentence explaining the link
- scc_action: what SCC should do about this connection

If no tenders match, state this is a FUTURE SIGNAL — no tender yet but expected.
Respond in JSON only. Return {"links": [...]}"""


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


def _find_matching_tenders(db: Session, article: NewsArticle, intel: NewsIntelligence):
    """Search for tenders matching a news article by entity name and keywords."""
    matches = []
    title_words = (article.title or "").split()
    # Extract meaningful keywords (4+ chars, not common words)
    stopwords = {"with", "from", "will", "that", "this", "have", "been", "were", "their", "about", "oman"}
    keywords = [w for w in title_words if len(w) >= 4 and w.lower() not in stopwords][:5]

    # Search by entity name in tender entity fields
    q = db.query(Tender)
    found = set()

    for kw in keywords:
        pattern = f"%{kw}%"
        results = q.filter(
            (Tender.tender_name_en.ilike(pattern)) |
            (Tender.entity_en.ilike(pattern))
        ).limit(5).all()
        for t in results:
            if t.tender_number not in found:
                found.add(t.tender_number)
                matches.append({
                    "tender_number": t.tender_number,
                    "tender_name": t.tender_name_en or t.tender_name_ar or "",
                    "entity": t.entity_en or t.entity_ar or "",
                    "category": t.category_en or "",
                })

    return matches[:10]


def link_news_to_tenders(db: Session) -> dict:
    """Link HIGH/MEDIUM priority news articles to matching tenders."""
    # Get analysed articles with HIGH or MEDIUM priority
    intel_articles = (
        db.query(NewsArticle, NewsIntelligence)
        .join(NewsIntelligence, NewsArticle.id == NewsIntelligence.article_id)
        .filter(NewsIntelligence.priority.in_(["HIGH", "MEDIUM"]))
        .all()
    )

    if not intel_articles:
        return {"status": "no_priority_articles", "linked": 0}

    # Skip articles already linked
    already_linked = set(
        r[0] for r in db.query(NewsTenderLink.article_id).all()
    )

    to_process = [(a, i) for a, i in intel_articles if a.id not in already_linked]
    if not to_process:
        return {"status": "all_linked", "linked": 0}

    linked = 0
    for article, intel in to_process[:20]:  # Process max 20 at a time
        matching_tenders = _find_matching_tenders(db, article, intel)

        user_content = json.dumps({
            "article": {
                "id": article.id,
                "title": article.title,
                "summary": article.summary or "",
                "source": article.source,
                "scc_implication": intel.scc_implication or "",
                "priority": intel.priority,
            },
            "potential_tenders": matching_tenders,
        }, ensure_ascii=False)

        result = _call_groq_json(LINKER_SYSTEM_PROMPT, user_content)

        if not result:
            continue

        links = result if isinstance(result, list) else result.get("links", [])

        for link in links:
            tender_number = link.get("tender_number", "")
            db.add(NewsTenderLink(
                article_id=article.id,
                tender_number=tender_number if tender_number else None,
                match_confidence=link.get("match_confidence", "possible"),
                connection=link.get("connection", ""),
                scc_action=link.get("scc_action", ""),
            ))
            linked += 1

        # If no matches found, still record as future signal
        if not links:
            db.add(NewsTenderLink(
                article_id=article.id,
                tender_number=None,
                match_confidence="future_signal",
                connection="No active tender found — this is a future opportunity signal.",
                scc_action="Monitor entity for upcoming tender publication.",
            ))
            linked += 1

        db.commit()

    return {"status": "success", "linked": linked}
