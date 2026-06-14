#!/bin/bash
LOG="/opt/scc-dashboard/scripts/daily-refresh.log"
API="http://localhost:8000/api"
BACKEND="/opt/scc-dashboard/repo/backend"
FAILED=0

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

# Run AI jobs with failure detection
for job in "tenders/score" "news/analyse" "competitive-intel/build-profiles" "entity-intel/build" "news/link-to-tenders" "briefings/generate"; do
  echo "$job..." >> $LOG

  # Capture both response body and HTTP status code
  HTTP_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API/$job" 2>&1)
  HTTP_STATUS=$(echo "$HTTP_RESPONSE" | tail -n1)
  BODY=$(echo "$HTTP_RESPONSE" | sed '$d')

  echo "$BODY" >> $LOG
  echo "" >> $LOG

  # Hard fail: non-2xx status
  if ! echo "$HTTP_STATUS" | grep -qE '^2[0-9]{2}$'; then
    echo ">>> REFRESH FAILED: $job (HTTP $HTTP_STATUS)" | tee -a $LOG
    FAILED=1
  # Hard fail: response body signals failure
  elif echo "$BODY" | grep -qE 'llm_failed|"status":"failed"'; then
    echo ">>> REFRESH FAILED: $job (job reported failure in response)" | tee -a $LOG
    FAILED=1
  else
    # Soft warning: success but 0 records processed
    if echo "$BODY" | grep -qE '(scored|analysed|analyzed|built|linked|generated|processed)[":]?\s*0[^0-9]'; then
      echo ">>> WARNING: $job returned 0 records" | tee -a $LOG
    fi
  fi

  sleep 5
done

if [ $FAILED -ne 0 ]; then
  echo "=== Daily refresh FAILED: $(date) ===" >> $LOG
  exit 1
else
  echo "=== Daily refresh completed: $(date) ===" >> $LOG
  exit 0
fi
