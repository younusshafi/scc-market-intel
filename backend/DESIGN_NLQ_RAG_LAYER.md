# Phase 2 Design Note: News-RAG Layer for NLQ

## What gets embedded (and what doesn't)

**Embed:** `news_articles` (title + summary) and `news_intelligence` (scc_implication).
These are free-text fields where keyword search fails on semantic questions like
"what infrastructure risks should we worry about?" or "any competitor JV activity?"

**Do NOT embed:** `tenders`, `awarded_tenders`, `tender_scores`, `entity_intelligence`,
`competitor_profiles`. These are structured/numeric — SQL handles them perfectly.
Embedding them would waste storage and produce worse answers than exact queries.

## Vector store: sqlite-vec vs local FAISS

| Criteria | sqlite-vec | FAISS (local) |
|----------|-----------|---------------|
| Deployment | Single file, same DB | Separate index file |
| Dependencies | C extension (pip install sqlite-vec) | pip install faiss-cpu |
| Query integration | SQL-native: `SELECT ... WHERE vec_distance(...)` | Python-side: search, then join IDs back to SQLite |
| Maturity | Newer, less battle-tested | Very mature, widely used |
| Fits SQLite stack? | Yes — zero new infra | Yes — but two data stores |

**Recommendation: FAISS (local).** sqlite-vec is appealing but still pre-1.0 and
the Windows build story is rough. FAISS-cpu is pip-installable everywhere, the
index is a single file (`news_embeddings.faiss` + `news_id_map.json`), and the
4,700-article corpus fits entirely in RAM (~20MB at 1536-dim). No Postgres
migration needed.

## Embedding generation and freshness

- **Model:** OpenAI `text-embedding-3-small` (1536 dims, $0.02/1M tokens).
  Entire corpus ~4,700 articles * ~200 tokens avg = ~940K tokens = ~$0.02 one-time.
- **Initial build:** Batch-embed all `news_articles` rows, store vectors in FAISS
  index with article IDs as keys.
- **Incremental update:** After each news scrape job, embed only new articles
  (WHERE `id > last_embedded_id`). Append to FAISS index. A daily cron addition
  of ~5-20 articles costs fractions of a cent.
- **Storage:** `data/news_embeddings.faiss` + `data/news_id_map.json` alongside
  `scc_intel.db`. Rebuild from scratch takes <60s.

## Router decision: SQL vs RAG per question

The NLQ router would add a **Tier 0.5** check before Tier 1 pattern matching:

```
Question arrives
  -> Tier 0.5: Is this a "vibe" / sentiment / thematic question about news?
     Heuristic keywords: "news", "articles", "reports", "risk", "sentiment",
     "what's happening", "JV", "joint venture", "market mood", "outlook"
     If yes -> RAG path (embed question, FAISS top-k, narrate from articles)
  -> Tier 1: Pattern match (SQL) — unchanged
  -> Tier 2: LLM SQL generation — unchanged
```

The RAG answer format would include the source article titles/links for
auditability, matching the anti-hallucination standard.

## Which Joseph questions need RAG vs SQL full-text search?

| Question type | SQL LIKE/FTS enough? | Needs RAG? |
|--------------|---------------------|------------|
| "news mentioning Galfar" | Yes — keyword match | No |
| "recent news about road projects" | Mostly — LIKE '%road%' | Borderline |
| "what infrastructure risks are emerging?" | No | Yes |
| "any competitor JV activity?" | Partial (is_jv_mention flag) | Yes — for context |
| "what's the market sentiment on construction?" | No | Yes |
| "has anyone reported on the Duqm port expansion?" | Partial | Yes — semantic match |

**Bottom line:** ~60% of news questions are keyword-searchable (and already work
via Tier 1 pattern `news mentioning X`). RAG adds value for the ~40% that are
semantic/thematic. The Tier 1/2 SQL architecture does NOT block the RAG layer —
it slots in cleanly as a parallel path.

## Architecture compatibility

The current Tier 1/2 build is RAG-ready:
- `nlq_service.ask()` is the single entry point — RAG would be a new branch
  inside it, not a separate endpoint.
- The response schema (`answer`, `sql`, `rows`, `tier`) extends naturally:
  RAG responses would use `tier=0` (or a new `"rag"` value), `sql=""`,
  and `rows` would contain the matched article snippets.
- No schema changes needed. No new tables. Just a new service file
  (`rag_service.py`) and a FAISS index file.
