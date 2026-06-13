#!/bin/bash
LOG="/opt/scc-dashboard/scripts/daily-refresh.log"
API="http://localhost:8000/api"
BACKEND="/opt/scc-dashboard/repo/backend"

echo "=== Daily refresh started: $(date) ===" >> $LOG

# Run news scraper
echo "Scraping news..." >> $LOG
cd $BACKEND
source venv/bin/activate
python -c "
from app.core.database import SessionLocal
from app.scrapers.news_scraper import scrape_all_news, persist_news
articles = scrape_all_news()
db = SessionLocal()
result = persist_news(db, articles)
print(result)
db.close()
" >> $LOG 2>&1

# Scrape new tenders
echo "Scraping new tenders..." >> $LOG
cd $BACKEND
source venv/bin/activate
python -m app.jobs.scrape_tenders >> $LOG 2>&1

sleep 5

# Run AI jobs
for job in "tenders/score" "news/analyse" "competitive-intel/build-profiles" "entity-intel/build" "news/link-to-tenders" "briefings/generate"; do
  echo "$job..." >> $LOG
  curl -s -X POST "$API/$job" >> $LOG 2>&1
  echo "" >> $LOG
  sleep 5
done

echo "=== Daily refresh completed: $(date) ===" >> $LOG
