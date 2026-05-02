# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SCC Market Intelligence Module — an AI-powered tender and market intelligence dashboard for Sarooj Construction Company (SCC), a Tier-1 Omani civil infrastructure contractor (roads, bridges, dams, marine works, pipelines). Tracks 4,500+ tenders from the Oman Tender Board and monitors 8 competitors: Galfar, Strabag, Al Tasnim, L&T, Towell, Hassan Allam, Arab Contractors, Ozkar.

## Commands

### Backend

```bash
cd backend

# Start API server (hot reload)
python -m uvicorn app.main:app --reload --port 8000

# Seed database from JSON files (run from backend/)
python -m scripts.seed_from_json --data-dir ../

# Run individual AI jobs
python -m app.jobs.score_tenders
python -m app.jobs.analyse_news
python -m app.jobs.generate_briefing
python -m app.jobs.build_competitor_profiles
python -m app.jobs.build_entity_intel
python -m app.jobs.link_news_to_tenders
python -m app.jobs.probe_tenders

# Run scrapers
python -m app.jobs.scrape_tenders
python -m app.jobs.scrape_news
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # Dev server at http://localhost:5173
npm run build        # Production build to dist/
```

### Database

- Local dev uses SQLite (`backend/scc_intel.db`), production uses PostgreSQL
- Tables auto-created on startup via `Base.metadata.create_all()`
- Column migrations for PostgreSQL handled in `app/main.py:_run_column_migrations()`
- Seed script has two phases: Phase 1 loads `tenders.json` + `historical_tenders.json`, Phase 2 loads probe data from `major_project_intelligence.json` + `competitor_intelligence.json`

## Architecture

**Backend** (FastAPI + SQLAlchemy):
- `app/api/` — REST routers mounted at `/api/{domain}/` (tenders, news, briefings, competitive-intel, entity-intel, geo, query, system)
- `app/services/` — Business logic and AI services. All LLM calls go through `llm_client.py` (OpenAI GPT-4o-mini)
- `app/scrapers/` — Oman Tender Board portal scraper, news RSS feeds, deep tender probe (bidders/purchasers/NIT)
- `app/jobs/` — Standalone job runners that import services and execute them
- `app/models/models.py` — All 11 SQLAlchemy models in one file
- `app/core/` — Database connection (`database.py`) and pydantic settings (`config.py`)

**Frontend** (React + Vite + Tailwind):
- 5-tab layout: Command Centre, Competitive Intel, Opportunities, Market & News, Profiles
- All data fetched on page load (no re-fetch on tab switch)
- `src/utils/api.js` — API client; API_BASE is `http://localhost:8000/api`
- `src/hooks/useAPI.jsx` — Custom hook for data fetching
- Vite proxies `/api/*` to backend in dev mode

**Data Flow**: Scrapers → DB → Services (AI enrichment) → API endpoints → Frontend

## Key Design Decisions

- **LLM calls centralized** in `app/services/llm_client.py`. Two functions: `call_llm()` (text) and `call_llm_json()` (structured JSON with `response_format`). To switch models, change `DEFAULT_MODEL` in this one file.
- **Competitor resolution** uses `competitive_intel_service.py:resolve_competitor()` — exact alias match first (TRACKED_ALIASES), then keyword match (COMPETITORS dict). Used across all intelligence services.
- **SQLite/PostgreSQL compatibility** — avoid PostgreSQL-specific functions (e.g., `date_trunc`). The trend endpoint uses Python `defaultdict` grouping instead. Column migrations skip on SQLite since `create_all` handles fresh DBs.
- **Tender scoring hard constraints** — Second/Third grade capped at 35, low-fee (<50 OMR) capped at 20, regardless of LLM output.
- **Major Project Tracker filters** — Excludes consulting, supply, IT, training categories and consultancy/furniture/cleaning titles. Only includes fee >= 200 OMR with SCC-relevant category OR tracked competitors present.
- **News deduplication** — Title word overlap > 0.5 = duplicate; keeps more authoritative source (Oman Observer > Times of Oman > Google News).

## Environment Variables

Required in `backend/.env`:
```
DATABASE_URL=sqlite:///./scc_intel.db
OPENAI_API_KEY=sk-...
```

Optional:
```
GROQ_API_KEY=gsk_...        # Legacy, not actively used
ENVIRONMENT=development
CORS_ORIGINS=["http://localhost:5173"]
```

## Domain Context

- SCC = Sarooj Construction Company (the client). SCC IS Sarooj — never profile Sarooj as a competitor.
- Fee values are in OMR (Omani Rial). Fee >= 200 OMR indicates a major project.
- Tender Board portal uses session-based auth with hash-constructed URLs for deep probing.
- "SCC-relevant" means: matching grade (Excellent/First), matching category (roads, bridges, marine, etc.), fee threshold met.
