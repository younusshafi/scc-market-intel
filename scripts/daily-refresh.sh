#!/usr/bin/env bash
# daily-refresh.sh — Run all daily data refresh jobs for SCC Market Intelligence Dashboard
# Intended to be run by cron at 02:00 UTC (06:00 Oman time)
set -e

REPO="/opt/scc-dashboard/repo"
VENV="$REPO/backend/venv/bin/activate"
LOG_DIR="/var/log"

cd "$REPO/backend"
# shellcheck disable=SC1090
source "$VENV"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting daily refresh..."

# 1. Scrape live tenders from Oman Tender Board
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Scraping tenders..."
python -m app.jobs.scrape_tenders >> "$LOG_DIR/scc-scraper.log" 2>&1

# 2. Scrape awarded tenders (incremental — only new since last run)
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Scraping awarded tenders (incremental)..."
python -m app.jobs.scrape_awarded_tenders >> "$LOG_DIR/scc-scraper.log" 2>&1

# 3. Scrape news
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Scraping news..."
python -m app.jobs.scrape_news >> "$LOG_DIR/scc-news.log" 2>&1

# 4. Probe high-value tenders for bidder intelligence
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Probing tenders..."
python -m app.jobs.probe_tenders >> "$LOG_DIR/scc-scraper.log" 2>&1

# 5. Score SCC-relevant tenders
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Scoring tenders..."
python -m app.jobs.score_tenders >> "$LOG_DIR/scc-scraper.log" 2>&1

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Daily refresh complete."
