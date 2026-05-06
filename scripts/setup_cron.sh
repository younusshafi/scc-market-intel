#!/usr/bin/env bash
# setup_cron.sh — Install SCC dashboard cron jobs on VPS
# Run as root on Ubuntu 24.04 at /opt/scc-dashboard/repo/
set -e

REPO="/opt/scc-dashboard/repo"
VENV="$REPO/backend/venv/bin/activate"
LOG_DIR="/var/log"

# Create log files
for log in scc-scraper.log scc-news.log scc-galfar.log scc-briefing.log; do
    touch "$LOG_DIR/$log"
    chmod 644 "$LOG_DIR/$log"
done
echo "Log files ready in $LOG_DIR"

# Helper: add cron job only if it doesn't already exist
add_cron() {
    local entry="$1"
    local label="$2"
    if crontab -l 2>/dev/null | grep -qF "$entry"; then
        echo "  SKIP (already exists): $label"
    else
        (crontab -l 2>/dev/null; echo "$entry") | crontab -
        echo "  ADDED: $label"
    fi
}

echo "Installing cron jobs..."

# Daily tender scraping — 6 AM Oman time (UTC+4) = 2 AM UTC
add_cron \
    "0 2 * * * cd $REPO/backend && source $VENV && python -m app.jobs.scrape_tenders >> $LOG_DIR/scc-scraper.log 2>&1" \
    "Daily tender scrape (06:00 Oman / 02:00 UTC)"

# News scraping — every 6 hours
add_cron \
    "0 */6 * * * cd $REPO/backend && source $VENV && python -m app.jobs.scrape_news >> $LOG_DIR/scc-news.log 2>&1" \
    "News scrape every 6h"

# Weekly Galfar MSX scraping — Monday 7 AM Oman time = 3 AM UTC
add_cron \
    "0 3 * * 1 cd $REPO/backend && source $VENV && python -m app.jobs.scrape_galfar >> $LOG_DIR/scc-galfar.log 2>&1" \
    "Weekly Galfar scrape (Mon 07:00 Oman / 03:00 UTC)"

# Weekly briefing generation — Monday 8 AM Oman time = 4 AM UTC
add_cron \
    "0 4 * * 1 cd $REPO/backend && source $VENV && python -m app.jobs.generate_briefing >> $LOG_DIR/scc-briefing.log 2>&1" \
    "Weekly briefing generation (Mon 08:00 Oman / 04:00 UTC)"

echo ""
echo "Current crontab:"
crontab -l
echo ""
echo "Done. Verify with: crontab -l"
