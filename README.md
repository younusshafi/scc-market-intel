# SCC Market Intelligence Module

Tender and market intelligence dashboard for Sarooj Construction Company (SCC).  
Built by [Zavia-ai](https://zavia-ai.com).

## Architecture

```
backend/          FastAPI + SQLAlchemy + PostgreSQL
  app/
    api/          REST endpoints (tenders, news, briefings, system)
    scrapers/     Tender Board + news RSS scrapers
    models/       SQLAlchemy ORM models
    jobs/         Cron job entry points
    core/         Config, database connection

frontend/         React + Vite + Tailwind CSS
  src/
    components/   Dashboard UI components
    hooks/        Custom React hooks
    utils/        API client

render.yaml       Render Blueprint (one-click deploy)
```

## Local Development

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt

# Create .env from template
cp .env.example .env
# Edit .env with your database URL and API keys

# Run the API
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Dashboard will be at `http://localhost:5173` (proxies API calls to port 8000).

### Database

Create a local PostgreSQL database:

```bash
createdb scc_intel
```

Tables are auto-created on first API startup in development mode.

### Running Scrapers Manually

```bash
cd backend
python -m app.jobs.scrape_tenders
python -m app.jobs.scrape_news
```

## Deploy to Render

1. Push this repo to GitHub
2. In Render dashboard → **New** → **Blueprint**
3. Connect your GitHub repo
4. Render reads `render.yaml` and creates all services automatically
5. Set environment variables (GROQ_API_KEY) in the Render dashboard

## Data Sources

- **Oman Tender Board**: etendering.tenderboard.gov.om (public portal, no auth)
- **Oman Observer**: RSS feeds (Home, News, Business)
- **Times of Oman**: RSS feed
- **Google News**: RSS search alerts for competitors and Oman construction/infrastructure
