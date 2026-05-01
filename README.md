# SCC Market Intelligence Module

AI-powered tender and market intelligence dashboard for Sarooj Construction Company (SCC).  
Built by [Zavia-ai](https://zavia-ai.com).

## Architecture

```
backend/          FastAPI + SQLAlchemy + SQLite (local) / PostgreSQL (prod)
  app/
    api/          REST endpoints (tenders, news, briefings, competitive-intel, geo, entity-intel)
    scrapers/     Tender Board scraper + news RSS + deep tender probe
    services/     AI services (scoring, briefing, competitive intel, news intelligence)
    models/       SQLAlchemy ORM models (10 tables)
    jobs/         Job runners (scoring, briefing, probing, profiling)
    core/         Config, database connection

frontend/         React + Vite + Tailwind CSS + Lucide icons
  src/
    components/   Dashboard UI (15+ components)
    hooks/        Custom React hooks (useAPI)
    utils/        API client

archive/          Legacy standalone scripts (reference only)
```

## Features

### Core Intelligence
- **Tender Pipeline** — 4,500+ tenders from Oman Tender Board, bilingual (EN/AR)
- **Competitive Battlefield** — Major project tracker, head-to-head bid comparisons, live competition monitoring
- **Executive Briefing** — AI-generated weekly briefing with competitor names, bid values, market trends
- **Geographic Distribution** — SVG map showing tender concentration by governorate

### AI-Powered Layers (Groq LLM)
- **AI Tender Match Scoring** — Scores 0-100 for SCC fit, with recommendations (MUST_BID / STRONG_FIT / CONSIDER / WATCH / SKIP)
- **AI News Intelligence** — Categorizes news by priority, generates SCC-specific implications
- **Competitor Behaviour Profiles** — AI analysis of each competitor's bidding patterns and threat level
- **Entity Intelligence** — Strategic assessment of government entities' tender behaviour
- **News-to-Tender Cross-Reference** — Links news articles to matching active tenders

### Data Features
- **Deep Tender Probing** — Extracts bidders, bid values, document purchasers, NIT details from portal
- **JV/Consortium Detection** — Identifies joint venture mentions in news
- **Re-Tender Radar** — Flags re-floated tenders with pattern insights
- **News Relevance Filtering** — Oman-context filter removes irrelevant international articles

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+
- Groq API key (free at https://console.groq.com)

### Backend Setup

```bash
cd backend

# Create .env
cat > .env << 'EOF'
DATABASE_URL=sqlite:///./scc_intel.db
GROQ_API_KEY=your_groq_api_key_here
ENVIRONMENT=development
EOF

# Install dependencies
pip install -r requirements.txt

# Seed the database (Phase 1: tenders, Phase 2: probe data)
python -m scripts.seed_from_json --data-dir ../

# Start the API server
python -m uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Dashboard at http://localhost:5173, API at http://localhost:8000.

### Running AI Jobs

```bash
# Generate executive briefing
curl -X POST http://localhost:8000/api/briefings/generate

# Score SCC-relevant tenders (0-100)
curl -X POST http://localhost:8000/api/tenders/score

# Analyse news articles for SCC implications
curl -X POST http://localhost:8000/api/news/analyse

# Build competitor behaviour profiles
curl -X POST http://localhost:8000/api/competitive-intel/build-profiles

# Build entity strategic intelligence
curl -X POST http://localhost:8000/api/entity-intel/build

# Link news articles to matching tenders
curl -X POST http://localhost:8000/api/news/link-to-tenders

# Backfill news relevance (re-filter existing articles)
curl -X POST http://localhost:8000/api/system/backfill-relevance
```

### Running Scrapers

```bash
cd backend

# Scrape tenders from Oman Tender Board
python -m app.jobs.scrape_tenders

# Scrape news from RSS feeds
python -m app.jobs.scrape_news

# Deep probe tender details (bidders, purchasers, NIT) — long running
python -m app.jobs.probe_tenders
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tenders/` | GET | List tenders (filter by scc_only, search, view) |
| `/api/tenders/stats` | GET | Dashboard statistics |
| `/api/tenders/trend` | GET | Monthly volume trend |
| `/api/tenders/scored` | GET | AI-scored tenders (sorted by score) |
| `/api/tenders/score` | POST | Trigger AI scoring job |
| `/api/competitive-intel/` | GET | Major projects, head-to-head, live competition, activity |
| `/api/competitive-intel/profiles` | GET | AI competitor behaviour profiles |
| `/api/competitive-intel/build-profiles` | POST | Build competitor profiles |
| `/api/entity-intel/` | GET | Entity strategic intelligence |
| `/api/entity-intel/build` | POST | Build entity intelligence |
| `/api/news/` | GET | List news articles |
| `/api/news/intelligence` | GET | AI-analysed news with SCC implications |
| `/api/news/analyse` | POST | Trigger news analysis |
| `/api/news/tender-links` | GET | News-to-tender cross-references |
| `/api/news/link-to-tenders` | POST | Link news to tenders |
| `/api/briefings/latest` | GET | Latest executive briefing |
| `/api/briefings/generate` | POST | Generate new briefing |
| `/api/geo/distribution` | GET | Geographic distribution of tenders |
| `/api/query/` | GET | Natural language query (?q=...) |
| `/api/system/health` | GET | Health check |
| `/api/system/scrape-status` | GET | Scraper status |
| `/api/system/run-probe` | POST | Trigger deep tender probe |

## Database Tables

| Table | Purpose |
|-------|---------|
| `tenders` | All tenders from Tender Board (4,500+ records) |
| `tender_probes` | Deep probe data: bidders, purchasers, NIT (96 records) |
| `tender_scores` | AI match scores per tender |
| `news_articles` | Scraped news from RSS feeds |
| `news_intelligence` | AI analysis of news articles |
| `news_tender_links` | Cross-references between news and tenders |
| `briefings` | AI-generated executive briefings |
| `competitor_profiles` | AI competitor behaviour profiles |
| `entity_intelligence` | AI entity strategic assessments |
| `competitor_mentions` | Competitor mention tracking |
| `scrape_logs` | Scraper run history |

## Key Data

- **Tracked Competitors**: Galfar, Strabag, Al Tasnim, L&T, Towell, Hassan Allam, Arab Contractors, Ozkar
- **SCC Categories**: Construction, Ports, Roads, Bridges, Pipeline, Electromechanical, Dams, Marine
- **SCC Grades**: Excellent, First, Second
- **Confirmed Bid**: Sarooj OMR 7,350,547 on Sohar Link Road vs Al Tasnim OMR 7,999,537 (+8.8%)

## Data Sources

- **Oman Tender Board**: etendering.tenderboard.gov.om (public portal)
- **Oman Observer**: RSS feeds (Home, News, Business)
- **Times of Oman**: RSS feed
- **Google News**: RSS search alerts for competitors and Oman construction/infrastructure
- **Groq API**: LLM intelligence (llama-3.3-70b-versatile)

## Groq API Limits

Free tier: 100,000 tokens/day. Running all AI jobs uses ~40-60K tokens.
If rate limited, wait for daily reset or upgrade at https://console.groq.com/settings/billing.
