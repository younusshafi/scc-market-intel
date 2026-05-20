"""
Galfar Financial Data Extractor — Stage 2
==========================================
Reads raw text files from scraped_data/galfar_raw/
Extracts structured financials using regex — no LLM needed.
The MSX report format is consistent across all periods.

Usage:
    python extract_galfar_financials.py

Output:
    scraped_data/galfar_financials_structured.json

Author: Zavia-ai for SCC Market Intelligence
"""

import re
import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

SCRAPED_DATA = Path(__file__).resolve().parent / "scraped_data"
RAW_DIR      = SCRAPED_DATA / "galfar_raw"
INDEX_PATH   = SCRAPED_DATA / "galfar_reports.json"
OUTPUT_PATH  = SCRAPED_DATA / "galfar_financials_structured.json"


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

def find_table_value(text: str, label: str, column: int = 0) -> int | None:
    """
    Find a row in the financial tables by label, return the Nth numeric value.
    The tables have format: Label  val1  val2  val3  val4
    column=0 → first value (consolidated current period)
    column=1 → second value (standalone/parent current period)
    """
    # Escape special chars in label for regex
    escaped = re.escape(label)
    # Match label then capture up to 4 numeric values (with commas, parens for negatives)
    pattern = rf"{escaped}\s+([\d,]+|\([\d,]+\))\s+([\d,]+|\([\d,]+\))\s+([\d,]+|\([\d,]+\))?\s*([\d,]+|\([\d,]+\))?"
    match = re.search(pattern, text)
    if not match:
        return None
    raw = match.group(column + 1)
    if not raw:
        return None
    # Handle negative values in parentheses
    negative = raw.startswith("(")
    cleaned = raw.replace("(", "").replace(")", "").replace(",", "")
    try:
        val = int(cleaned) * 1000  # Values are in RO 000
        return -val if negative else val
    except ValueError:
        return None


def find_narrative_value(text: str, pattern: str) -> int | None:
    """
    Extract a value from narrative text (e.g. 'order backlog of approximately OMR 702 million').
    Returns value in OMR (not thousands).
    """
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return None
    num_str = match.group(1).replace(",", "")
    try:
        return int(float(num_str) * 1_000_000)
    except ValueError:
        return None


def extract_period_dates(text: str) -> tuple[str | None, str | None]:
    """Extract period end date and report approval date."""
    period_end = None
    report_date = None

    # Period end from header: "31/03/2026" or "31/12/2025"
    m = re.search(r"for (?:the )?(?:period|quarter|year) ended[^\d]*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4})", text, re.IGNORECASE)
    if m:
        d = m.group(1)
        if "/" in d:
            parts = d.split("/")
            period_end = f"{parts[2]}-{parts[1]}-{parts[0]}"
        else:
            period_end = d

    # Also try INTERIM CONDENSED header
    if not period_end:
        m = re.search(r"STATEMENTS,\s*(\d{2}/\d{2}/\d{4})", text)
        if m:
            parts = m.group(1).split("/")
            period_end = f"{parts[2]}-{parts[1]}-{parts[0]}"

    # Report approval date
    m = re.search(r"APPROVED BY THE BOARD.*?ON\s+(\d{1,2}\s+\w+\s+\d{4}|\d{2}/\d{2}/\d{4}|\d{2}\s+\w{3}\s+\d{4})", text, re.IGNORECASE)
    if m:
        report_date = m.group(1).strip()

    return period_end, report_date


def extract_period_label(period_key: str) -> str:
    year, quarter = period_key.split("_", 1)
    labels = {
        "Q1": f"Q1 {year} (Un-Audited)",
        "Q2": f"Q2 {year} (Un-Audited)",
        "Q3": f"Q3 {year} (Un-Audited)",
        "Annual": f"Annual {year} (Audited)",
    }
    return labels.get(quarter, period_key)


def is_annual(period_key: str) -> bool:
    return "Annual" in period_key


# ---------------------------------------------------------------------------
# Main extraction per report
# ---------------------------------------------------------------------------

def split_sections(text: str) -> dict:
    """
    Split raw text into named sections by PDF filename markers.
    Returns dict keyed by PDF type: company_report, income_statement, balance_sheet
    """
    sections = {"full": text}
    # Split on page markers like "=== 1_GECS_CompanyReport_* | Page 1 ==="
    import re as _re
    for label, pattern in [
        ("company_report",    r"=== 1_GECS_CompanyReport"),
        ("income_statement",  r"=== 3_GECS_IncomeStatement"),
        ("balance_sheet",     r"=== 2_GECS_BalanceSheet"),
        ("mgmt_discussion",   r"=== 9_GECS_ManagementDi"),
    ]:
        idx = text.find(pattern.replace("r", "").strip('"'))
        # Use regex search instead
        m = _re.search(pattern, text)
        if m:
            sections[label] = text[m.start():]
    return sections


def extract_report(period_key: str, text: str) -> dict:
    result = {
        "period":       period_key,
        "label":        extract_period_label(period_key),
        "is_annual":    is_annual(period_key),
    }

    period_end, report_date = extract_period_dates(text)
    result["period_end_date"] = period_end
    result["report_date"]     = report_date

    sections = split_sections(text)

    # --- Income Statement (use IncomeStatement section for accuracy) ---
    # Format: Consolidated current | Standalone current | Consolidated prior | Standalone prior
    income_text = sections.get("income_statement", text)

    revenue_group  = find_table_value(income_text, "Total revenue", column=0)
    revenue_parent = find_table_value(income_text, "Total revenue", column=1)
    # Fallback to plain Revenue label
    if revenue_group is None:
        revenue_group  = find_table_value(income_text, "Revenue", column=0)
        revenue_parent = find_table_value(income_text, "Revenue", column=1)
    result["revenue_group_omr"]  = revenue_group
    result["revenue_parent_omr"] = revenue_parent

    gross_profit_group  = find_table_value(income_text, "Gross profit", column=0)
    gross_profit_parent = find_table_value(income_text, "Gross profit", column=1)
    result["gross_profit_group_omr"]  = gross_profit_group
    result["gross_profit_parent_omr"] = gross_profit_parent

    # EBITDA is only in CompanyReport summary table, parent first then consolidated
    company_text = sections.get("company_report", text)
    ebitda_parent = find_table_value(company_text, "EBITDA", column=0)
    ebitda_group  = find_table_value(company_text, "EBITDA", column=1)
    result["ebitda_group_omr"]  = ebitda_group
    result["ebitda_parent_omr"] = ebitda_parent

    profit_group  = find_table_value(income_text, "Net Profit / (Loss) for the period", column=0)
    profit_parent = find_table_value(income_text, "Net Profit / (Loss) for the period", column=1)
    if profit_group is None:
        profit_group  = find_table_value(income_text, "Profit (loss) from continuing operations", column=0)
        profit_parent = find_table_value(income_text, "Profit (loss) from continuing operations", column=1)
    result["net_profit_group_omr"]  = profit_group
    result["net_profit_parent_omr"] = profit_parent

    # --- Balance Sheet ---
    total_assets_group  = find_table_value(text, "Total assets", column=0)
    total_assets_parent = find_table_value(text, "Total assets", column=1)
    result["total_assets_group_omr"]  = total_assets_group
    result["total_assets_parent_omr"] = total_assets_parent

    total_equity_group  = find_table_value(text, "Total equity", column=0)
    total_equity_parent = find_table_value(text, "Total equity", column=1)
    result["total_equity_group_omr"]  = total_equity_group
    result["total_equity_parent_omr"] = total_equity_parent

    # --- Narrative Extraction (backlog, awards, employees) ---
    # Backlog: "order backlog of approximately OMR 702 million"
    backlog = find_narrative_value(
        text,
        r"order backlog of approximately OMR ([\d,\.]+) million"
    )
    result["order_backlog_omr"] = backlog

    # New awards: "no new project awards" flag
    no_awards = bool(re.search(
        r"did not (?:secure|bag) any new project awards"
        r"|did not secure new project awards"
        r"|no new project awards",
        text, re.IGNORECASE
    ))
    result["no_new_awards"] = no_awards

    # Employees (Omani)
    emp_match = re.search(
        r"(?:close to|more than|approximately)\s+([\d,]+)\s+Oman",
        text, re.IGNORECASE
    )
    if emp_match and emp_match.group(1).strip():
        try:
            result["omani_employees"] = int(emp_match.group(1).replace(",", ""))
        except ValueError:
            result["omani_employees"] = None
    else:
        result["omani_employees"] = None

    # Major projects mentioned
    projects = []
    if re.search(r"UAE.Oman Railway", text, re.IGNORECASE):
        projects.append("UAE-Oman Railway Link (Abu Dhabi-Sohar) via NNGT JV")
    result["major_projects"] = projects

    # Notable strategic statements (pull key sentences)
    statements = []
    for pattern in [
        r"(did not (?:secure|bag) any new project awards[^.]+\.)",
        r"(no new project awards to Galfar over the past[^.]+\.)",
        r"(order backlog of approximately[^.]+\.)",
        r"(5,\d{3} Oman[^.]+\.)",
        r"(4,\d{3} Oman[^.]+\.)",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            statements.append(m.group(1).strip())
    result["notable_statements"] = statements[:4]

    result["extracted_at"] = datetime.utcnow().isoformat() + "Z"
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    log.info("=== Galfar Financial Extractor — Stage 2 ===")

    if not INDEX_PATH.exists():
        log.error("Index not found: %s — run scrape_galfar_reports.py first", INDEX_PATH)
        return

    index = json.loads(INDEX_PATH.read_text())
    reports = index.get("reports", {})
    log.info("Reports in index: %s", sorted(reports.keys()))

    structured = {}

    for period_key, meta in sorted(reports.items()):
        raw_path = Path(meta.get("raw_text_path", ""))
        if not raw_path.exists():
            log.warning("Raw file missing for %s: %s", period_key, raw_path)
            continue

        text = raw_path.read_text(encoding="utf-8")
        log.info("Extracting %s (%d chars)...", period_key, len(text))

        result = extract_report(period_key, text)
        structured[period_key] = result

        log.info(
            "  ✓ revenue_group=%.1fM  profit_group=%s  backlog=%s  no_awards=%s",
            (result.get("revenue_group_omr") or 0) / 1e6,
            f"{(result.get('net_profit_group_omr') or 0)/1e6:.1f}M" if result.get("net_profit_group_omr") is not None else "n/a",
            f"OMR {result.get('order_backlog_omr')/1e6:.0f}M" if result.get("order_backlog_omr") else "not found",
            result.get("no_new_awards"),
        )

    # Save
    output = {
        "symbol":       "GECS",
        "company":      "Galfar Engineering & Contracting SAOG",
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "periods":      structured,
    }
    OUTPUT_PATH.write_text(json.dumps(output, indent=2), encoding="utf-8")
    log.info("Saved to %s", OUTPUT_PATH)

    # Print summary table
    print("\n=== GALFAR FINANCIAL SUMMARY ===")
    print(f"{'Period':<20} {'Revenue (Grp)':<18} {'Net Profit':<16} {'Backlog':<16} {'No Awards'}")
    print("-" * 85)
    for k, v in sorted(structured.items()):
        rev  = f"OMR {v['revenue_group_omr']/1e6:.1f}M" if v.get("revenue_group_omr") else "-"
        prof = f"OMR {v['net_profit_group_omr']/1e6:.2f}M" if v.get("net_profit_group_omr") is not None else "-"
        back = f"OMR {v['order_backlog_omr']/1e6:.0f}M" if v.get("order_backlog_omr") else "-"
        na   = "YES" if v.get("no_new_awards") else "-"
        print(f"{k:<20} {rev:<18} {prof:<16} {back:<16} {na}")


if __name__ == "__main__":
    main()
