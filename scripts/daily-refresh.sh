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

# run_scraper <label> <logfile> <command...>
# Scrapers are not AI jobs, so they get no llm_failed/401 scan — but a hard
# (non-zero) exit should be visible, not silently swallowed by set -e. On
# failure, print a clear REFRESH FAILED marker and exit 1. (No zero-record
# detection: a legitimately quiet day must not false-alarm.)
run_scraper() {
    local label="$1" logfile="$2"; shift 2
    if ! "$@" >>"$logfile" 2>&1; then
        echo ">>> REFRESH FAILED: $label (hard error)" | tee -a "$logfile"
        exit 1
    fi
}

# run_ai_job <label> <logfile> <command...>
# AI jobs catch their own exceptions and exit 0 even on a 401 / llm_failed, so
# `set -e` never fires during an OpenAI outage and cron would falsely report
# success. Capture each job's output, append it to its log, then scan for
# failure markers; on a hit (or a hard non-zero exit) print a clear REFRESH
# FAILED marker and exit 1 so the outage is visible.
run_ai_job() {
    local label="$1" logfile="$2"; shift 2
    local out reason
    out="$(mktemp)"
    if ! "$@" >"$out" 2>&1; then
        cat "$out" >>"$logfile"
        echo ">>> REFRESH FAILED: $label (job exited non-zero)" | tee -a "$logfile"
        rm -f "$out"; exit 1
    fi
    cat "$out" >>"$logfile"
    if grep -qiE 'llm_failed|unauthorized|returned 401' "$out"; then
        reason="$(grep -ioE 'llm_failed|unauthorized|returned 401' "$out" | head -1)"
        echo ">>> REFRESH FAILED: $label ($reason)" | tee -a "$logfile"
        rm -f "$out"; exit 1
    fi
    rm -f "$out"
}

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Starting daily refresh..."

# 1. Scrape live tenders from Oman Tender Board
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Scraping tenders..."
run_scraper scrape_tenders "$LOG_DIR/scc-scraper.log" python -m app.jobs.scrape_tenders

# 2. Scrape news
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Scraping news..."
run_scraper scrape_news "$LOG_DIR/scc-news.log" python -m app.jobs.scrape_news

# 3. Probe high-value tenders for bidder intelligence
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Probing tenders..."
run_scraper probe_tenders "$LOG_DIR/scc-scraper.log" python -m app.jobs.probe_tenders

# --- AI enrichment (guarded: 401 / llm_failed -> ">>> REFRESH FAILED" + exit 1) ---

# 4. Score SCC-relevant tenders
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Scoring tenders..."
run_ai_job score_tenders "$LOG_DIR/scc-scraper.log" python -m app.jobs.score_tenders

# 5. Analyse news for strategic intelligence
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Analysing news..."
run_ai_job analyse_news "$LOG_DIR/scc-news.log" python -m app.jobs.analyse_news

# 6. Link news to tenders
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Linking news to tenders..."
run_ai_job link_news_to_tenders "$LOG_DIR/scc-news.log" python -m app.jobs.link_news_to_tenders

# 7. Build competitor profiles
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Building competitor profiles..."
run_ai_job build_competitor_profiles "$LOG_DIR/scc-scraper.log" python -m app.jobs.build_competitor_profiles

# 8. Build entity intelligence
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Building entity intelligence..."
run_ai_job build_entity_intel "$LOG_DIR/scc-scraper.log" python -m app.jobs.build_entity_intel

# 9. Generate executive briefing
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Generating briefing..."
run_ai_job generate_briefing "$LOG_DIR/scc-scraper.log" python -m app.jobs.generate_briefing

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Daily refresh complete."
