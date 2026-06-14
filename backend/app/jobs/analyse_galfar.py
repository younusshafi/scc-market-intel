"""
Galfar Financial Analyser — Stage 3
=====================================
Reads structured financials from galfar_financials_structured.json
plus raw narrative text from galfar_raw/
Sends to Groq LLM for strategic analysis from SCC's perspective.
Appends analysis back into galfar_financials_structured.json.

Run after extract_galfar_financials.py.

Usage:
    pip install requests python-dotenv
    python analyse_galfar.py

Author: Zavia-ai for SCC Market Intelligence
"""

import os
import json
import time
import logging
import requests
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not set in .env")

GROQ_MODEL   = "llama-3.3-70b-versatile"
GROQ_URL     = "https://api.groq.com/openai/v1/chat/completions"

SCRAPED_DATA = Path(__file__).resolve().parent / "scraped_data"
RAW_DIR      = SCRAPED_DATA / "galfar_raw"
STRUCTURED   = SCRAPED_DATA / "galfar_financials_structured.json"

# ---------------------------------------------------------------------------
# SCC context — fed to LLM so analysis is always from the SCC tendering/proposals team's perspective
# ---------------------------------------------------------------------------

SCC_CONTEXT = """
You are a competitive intelligence analyst working for Sarooj Construction Company (SCC),
an Omani civil infrastructure contractor specialising in roads, bridges, tunnels, and dams.

SCC's key facts:
- Genuine competitive territory: OMR 50M+ infrastructure tenders (MoTCIT, large municipal)
- Win rate at OMR 50M+: ~25% when genuinely competing
- Near misses against Galfar: lost by 3.5% on OMR 121M, 5.6% on OMR 123.5M (MoT highway packages)
- SCC's tendering/proposals team reviews this analysis to make bid/no-bid decisions

Galfar is SCC's primary large-scale competitor. Galfar facts you already know:
- Oman's largest civil contractor by revenue (~OMR 286M/year)
- Genuine territory: OMR 20M+ infrastructure (oil & gas, roads, utilities)
- Token bid rate 43% at small scale — ignore Galfar bids below OMR 5M
- Currently: no new project awards for 18 months (as of Q1 2026)
- Backlog declining: OMR 745M (end 2025) → OMR 702M (Q1 2026)
- Railway JV (UAE-Oman, Abu Dhabi-Sohar via NNGT) consuming capacity
- 5,000+ Omani employees — political pressure to win new work urgently
"""

ANALYSIS_PROMPT = """
Analyse the following Galfar financial report data from SCC's competitive intelligence perspective.

STRUCTURED DATA (extracted figures):
{structured}

NARRATIVE TEXT FROM REPORT (Directors report, MD&A):
{narrative}

Return ONLY valid JSON with exactly this structure:

{{
  "threat_level": "HIGH|MEDIUM|LOW",
  "threat_rationale": "one sentence explaining the threat level",

  "key_signals": [
    "signal 1 — specific, factual, quantified where possible",
    "signal 2",
    "signal 3"
  ],

  "backlog_trend": "GROWING|STABLE|DECLINING|UNKNOWN",
  "backlog_commentary": "one sentence on what the backlog movement means for Galfar's hunger/pricing",

  "capacity_assessment": "one sentence on whether Galfar has capacity to take on new large tenders",

  "scc_implication": "the single most important thing the SCC tendering/proposals team should know from this report",

  "bid_watch": "specific instruction — e.g. 'Watch Galfar doc purchases on any MoTCIT tender above OMR 20M'",

  "pricing_expectation": "AGGRESSIVE|NORMAL|SELECTIVE|UNKNOWN",
  "pricing_rationale": "why — link to backlog/awards situation",

  "new_awards_mentioned": [],
  "projects_mentioned": [],

  "analysis_period": "{period_label}",
  "analysed_at": "{now}"
}}

Rules:
- key_signals: max 5, ordered by importance to SCC, each must be actionable or decision-relevant
- ONLY reference figures that are explicitly stated in the structured data or narrative text provided
- If a field (e.g. order_backlog_omr) is null in the structured data, do NOT invent a backlog figure
- If no new awards are mentioned in the narrative, set new_awards_mentioned to [] and note it in key_signals
- backlog_trend: only GROWING/DECLINING if you have two actual backlog figures to compare; otherwise UNKNOWN
- pricing_expectation: AGGRESSIVE if backlog_omr is declining AND no_new_awards is true; SELECTIVE if backlog healthy; UNKNOWN if insufficient data
- Do NOT extrapolate, estimate, or fill in missing data — say UNKNOWN if data is absent
- Return ONLY the JSON object, no preamble or explanation
"""

# ---------------------------------------------------------------------------
# Groq call
# ---------------------------------------------------------------------------

def call_groq(system: str, user: str) -> str:
    resp = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": GROQ_MODEL,
            "temperature": 0.1,
            "max_tokens": 1500,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user",   "content": user}
            ]
        },
        timeout=60
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def parse_json_response(raw: str) -> dict:
    # Strip markdown fences if present
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Build narrative snippet from raw text
# Extracts the most signal-rich sections: CompanyReport + ManagementDiscussion
# ---------------------------------------------------------------------------

def get_narrative(period_key: str) -> str:
    raw_path = RAW_DIR / f"{period_key}.txt"
    if not raw_path.exists():
        return ""
    text = raw_path.read_text(encoding="utf-8")

    # Extract CompanyReport section (Directors report — has backlog, awards, outlook)
    import re
    company_match = re.search(r"=== 1_GECS_CompanyReport", text)
    income_match  = re.search(r"=== 2_GECS_BalanceSheet", text)  # stop before balance sheet

    narrative_parts = []

    if company_match:
        end = income_match.start() if income_match else len(text)
        narrative_parts.append(text[company_match.start():end])

    # Also grab ManagementDiscussion if present (annual reports only)
    mgmt_match = re.search(r"=== 9_GECS_ManagementDi", text)
    if mgmt_match:
        narrative_parts.append(text[mgmt_match.start():mgmt_match.start() + 8000])

    narrative = "\n\n".join(narrative_parts)

    # Truncate to ~6000 chars — LLM has context, but keep it focused
    if len(narrative) > 6000:
        narrative = narrative[:6000] + "\n\n[... truncated ...]"

    return narrative


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("=== Galfar Analyser — Stage 3: LLM Strategic Analysis ===")
    log.info("Model: %s", GROQ_MODEL)

    if not STRUCTURED.exists():
        log.error("Structured data not found — run extract_galfar_financials.py first")
        return

    data = json.loads(STRUCTURED.read_text(encoding="utf-8"))
    periods = data.get("periods", {})
    log.info("Periods to analyse: %s", sorted(periods.keys()))

    new_count = 0

    for period_key in sorted(periods.keys()):
        period_data = periods[period_key]

        # Skip if already analysed
        if period_data.get("analysis"):
            log.info("SKIP %s — already analysed", period_key)
            continue

        log.info("--- Analysing %s ---", period_key)

        narrative = get_narrative(period_key)
        if not narrative:
            log.warning("No narrative text for %s — skipping", period_key)
            continue

        # Build structured summary for LLM (just the numbers, clean)
        structured_summary = {
            k: v for k, v in period_data.items()
            if k not in ("extracted_at", "notable_statements", "major_projects")
        }

        user_prompt = ANALYSIS_PROMPT.format(
            structured=json.dumps(structured_summary, indent=2),
            narrative=narrative,
            period_label=period_data.get("label", period_key),
            now=datetime.now(timezone.utc).isoformat()
        )

        for attempt in range(3):
            try:
                if attempt > 0:
                    wait = 30 * attempt
                    log.info("  Retry %d — waiting %ds...", attempt, wait)
                    time.sleep(wait)
                raw = call_groq(SCC_CONTEXT, user_prompt)
                analysis = parse_json_response(raw)
                period_data["analysis"] = analysis
                log.info(
                    "  ✓ threat=%s  pricing=%s  backlog_trend=%s",
                    analysis.get("threat_level"),
                    analysis.get("pricing_expectation"),
                    analysis.get("backlog_trend"),
                )
                new_count += 1
                # Save after each success so partial runs are not lost
                data["last_analysed"] = datetime.now(timezone.utc).isoformat()
                STRUCTURED.write_text(json.dumps(data, indent=2), encoding="utf-8")
                time.sleep(8)  # Groq free tier: ~6 req/min, stay under
                break
            except requests.HTTPError as e:
                if e.response.status_code == 429:
                    log.warning("  Rate limited on attempt %d", attempt + 1)
                    if attempt == 2:
                        log.error("  ✗ Giving up on %s after 3 attempts", period_key)
                else:
                    log.error("  ✗ HTTP error for %s: %s", period_key, e)
                    break
            except Exception as e:
                log.error("  ✗ Failed for %s: %s", period_key, e)
                break

    # Save updated structured data
    data["last_analysed"] = datetime.now(timezone.utc).isoformat()
    STRUCTURED.write_text(json.dumps(data, indent=2), encoding="utf-8")
    log.info("Saved. %d new analyses added.", new_count)

    # Print analysis summary
    print("\n=== GALFAR STRATEGIC ANALYSIS SUMMARY ===")
    for period_key in sorted(periods.keys()):
        a = periods[period_key].get("analysis")
        if not a:
            continue
        print(f"\n{'='*60}")
        print(f"  {period_key}  |  Threat: {a.get('threat_level')}  |  Pricing: {a.get('pricing_expectation')}")
        print(f"  Backlog: {a.get('backlog_trend')}  —  {a.get('backlog_commentary','')}")
        print(f"  SCC Implication: {a.get('scc_implication','')}")
        print(f"  Bid Watch: {a.get('bid_watch','')}")
        print(f"  Key signals:")
        for s in a.get("key_signals", []):
            print(f"    • {s}")


if __name__ == "__main__":
    main()
