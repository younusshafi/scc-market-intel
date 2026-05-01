"""
News intelligence analysis service.
Uses Groq LLM to analyse news articles for SCC strategic implications.
"""

import json
import time
import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.services.llm_client import call_llm_json
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



def _normalize_title_words(title: str) -> set:
    """Extract significant words, removing source suffixes and stop words."""
    import re
    # Remove source attribution (e.g. "- ZAWYA", "- MEED")
    title = re.sub(r'\s*[-\u2013\u2014]\s*\w+\s*$', '', title)
    # Remove punctuation
    title = re.sub(r'[^\w\s]', ' ', title.lower())
    stop_words = {"the", "a", "an", "in", "on", "at", "to", "for", "of",
                  "and", "or", "is", "are", "was", "were", "has", "have",
                  "oman", "omans", "s"}
    words = set(title.split()) - stop_words
    return words


def _title_word_overlap(title1: str, title2: str) -> float:
    """Calculate word overlap ratio between two normalized titles."""
    words1 = _normalize_title_words(title1)
    words2 = _normalize_title_words(title2)
    if not words1 or not words2:
        return 0
    intersection = words1 & words2
    return len(intersection) / min(len(words1), len(words2))


# Source authority ranking (higher = more authoritative)
SOURCE_PRIORITY = {
    "oman observer": 3,
    "times of oman": 2,
    "google news": 1,
}


def _get_source_priority(source: str) -> int:
    low = (source or "").lower()
    for key, priority in SOURCE_PRIORITY.items():
        if key in low:
            return priority
    return 0


def _deduplicate_articles(articles: list) -> list:
    """Remove duplicate articles with >70% title word overlap, keeping more authoritative source."""
    if not articles:
        return articles

    keep = []
    for article in articles:
        is_dup = False
        for kept in keep:
            overlap = _title_word_overlap(article.title or "", kept.title or "")
            if overlap > 0.5:  # was 0.7 — catches more duplicates
                # Replace if new article is from more authoritative source
                if _get_source_priority(article.source) > _get_source_priority(kept.source):
                    keep.remove(kept)
                    keep.append(article)
                is_dup = True
                break
        if not is_dup:
            keep.append(article)

    return keep


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

    # Deduplicate by title similarity (>70% word overlap → keep more authoritative source)
    to_analyse = _deduplicate_articles(to_analyse)

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
        result = call_llm_json(NEWS_ANALYSIS_SYSTEM_PROMPT, user_content)

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
            time.sleep(0.5)  # Rate limit

    return {"status": "success", "analysed": analysed, "total_recent": len(recent_articles)}
