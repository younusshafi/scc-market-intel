"""
Natural-Language Query (NLQ) service for SCC Market Intelligence.

Two tiers:
  Tier 1 — deterministic pattern matching (no LLM, zero cost)
  Tier 2 — LLM-generated SQL with strict validation (fallback)
"""

import json
import logging
import re
import sqlite3
import time
from datetime import date, timedelta

import sqlglot

from app.core.config import get_settings
from app.services.llm_client import call_llm_json, call_llm

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_TABLES = {
    "tenders", "awarded_tenders", "tender_scores", "news_articles",
    "news_intelligence", "competitor_profiles", "entity_intelligence",
    "tender_probes",
}

DANGEROUS_KW = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|ATTACH|PRAGMA|CREATE|REPLACE)\b",
    re.IGNORECASE,
)

MULTI_STATEMENT = re.compile(r";")

LIMIT_CAP = 200
QUERY_TIMEOUT_S = 5

# Known SCC competitors (for pattern matching)
COMPETITORS = [
    "Galfar", "Strabag", "Al Tasnim", "L&T", "Towell",
    "Hassan Allam", "Arab Contractors", "Ozkar", "Premier International",
]

# Data caveats to surface when relevant
CAVEATS = {
    "scc_wins": (
        "Caveat: SCC win counts are likely understated — recalled/negotiated "
        "tenders awarded outside the Tender Board are not captured in this data."
    ),
    "win_rate": (
        "Caveat: Win rates are distorted by token bids (competitors bidding "
        "with no intent to win, inflating bidder counts)."
    ),
    "muscat_municipality": (
        "Caveat: Muscat Municipality wins attributed to SCC may include a "
        "sister company operating under the same umbrella."
    ),
}

# ---------------------------------------------------------------------------
# Schema description for LLM prompt
# ---------------------------------------------------------------------------

SCHEMA_PROMPT = """You are a SQL generator for an Oman construction tender database (SQLite).

TABLES AND COLUMNS (use ONLY these tables and columns):

tenders (8,400+ rows)
  id INTEGER PK, tender_number VARCHAR(100), tender_number_en VARCHAR(100),
  tender_name_ar TEXT, tender_name_en TEXT,
  entity_ar VARCHAR(300), entity_en VARCHAR(300),
  category_ar VARCHAR(200), category_en VARCHAR(200),
  grade_ar VARCHAR(100), grade_en VARCHAR(100),
  tender_type_ar VARCHAR(200), tender_type_en VARCHAR(200),
  sales_end_date DATE, bid_closing_date DATE, actual_opening_date DATE,
  fee FLOAT, bank_guarantee VARCHAR(50),
  "view" VARCHAR(50),  -- MUST be quoted, reserved word. Values: NewTenders, InProcessTenders, SubContractTenders
  is_retender BOOLEAN, is_scc_relevant BOOLEAN, is_subcontract BOOLEAN,
  parent_tender_number VARCHAR(100), parent_tender_name TEXT,
  first_seen DATETIME, last_seen DATETIME, scraped_at DATETIME

tender_scores (joins to tenders via tender_number VARCHAR, NOT integer FK)
  id INTEGER PK, tender_number VARCHAR(100), score INTEGER, recommendation VARCHAR(50),
  reasoning TEXT, scored_at DATETIME

awarded_tenders (28,500+ rows)
  id INTEGER PK, internal_id VARCHAR(50), tender_number VARCHAR(100),
  tender_title TEXT, entity VARCHAR(300), category VARCHAR(200), grade VARCHAR(200),
  awarded_date VARCHAR(50),  -- STORED AS STRING "DD-MM-YYYY HH:MM:SS" e.g. "29-04-2026 12:19:42"
  is_construction BOOLEAN,
  winner_company VARCHAR(300), winning_value FLOAT, num_bidders INTEGER,
  lowest_bid FLOAT, highest_bid FLOAT, bid_spread_pct FLOAT,
  bidders_json TEXT,  -- JSON array: [{"company":"...","quoted_value":...,"is_winner":true/false}]
  scraped_at DATETIME
  NOTE: There is NO runner_up column. All bidders are in bidders_json.

news_articles (4,700+ rows)
  id INTEGER PK, source VARCHAR(200), title TEXT, link TEXT,
  published DATETIME, summary TEXT,
  is_competitor_mention BOOLEAN, mentioned_competitors JSON,
  is_relevant BOOLEAN, is_jv_mention BOOLEAN, jv_details JSON,
  scraped_at DATETIME

news_intelligence
  id INTEGER PK, article_id INTEGER (FK to news_articles.id),
  relevant BOOLEAN, scc_implication TEXT, category VARCHAR(50),
  priority VARCHAR(20), analysed_at DATETIME

competitor_profiles
  id INTEGER PK, competitor_name VARCHAR(100), behaviour_summary TEXT,
  threat_level VARCHAR(20), scc_strategy TEXT, conversion_rate INTEGER,
  overlap_with_scc INTEGER, top_categories JSON, top_governorates JSON, built_at DATETIME

entity_intelligence
  id INTEGER PK, entity_name VARCHAR(300), total_tenders INTEGER,
  scc_relevant_count INTEGER, avg_fee FLOAT, strategic_value VARCHAR(20),
  insight TEXT, action TEXT, competitors_present JSON, top_categories JSON, built_at DATETIME

tender_probes (157 rows — only a subset of tenders have been deep-probed)
  id INTEGER PK, tender_number VARCHAR(100), tender_name TEXT,
  entity VARCHAR(300), category VARCHAR(200), fee FLOAT,
  "view" VARCHAR(50),  -- MUST be quoted, reserved word
  bidders JSON,  -- [{company, offer_type, quoted_value, status}]
  purchasers JSON,  -- [{company, purchase_date}]
  nit JSON,  -- {title, governorate, wilayat, envelope, ...}
  probed_at DATETIME, updated_at DATETIME

CRITICAL RULES:
1. Generate ONLY a single SELECT statement. No INSERT/UPDATE/DELETE/DROP/ALTER.
2. awarded_date is a STRING in "DD-MM-YYYY HH:MM:SS" format.
   - To extract year: SUBSTR(awarded_date, 7, 4)
   - To extract month: SUBSTR(awarded_date, 4, 2)
   - To compare dates, convert to YYYY-MM-DD: SUBSTR(awarded_date,7,4)||'-'||SUBSTR(awarded_date,4,2)||'-'||SUBSTR(awarded_date,1,2)
3. Always quote "view" with double quotes — it's a reserved word.
4. tender_scores joins to tenders on tender_number (VARCHAR), not integer FK.
5. SCC = "SAROOJ CONSTRUCTION COMPANY" in winner_company (uppercase).
6. To search inside bidders_json, use json_each: e.g.
   SELECT ... FROM awarded_tenders, json_each(awarded_tenders.bidders_json) AS j WHERE json_extract(j.value, '$.company') LIKE '%name%'
7. Limit results to 200 rows max. Always add LIMIT 200.
8. Use LIKE with % wildcards for fuzzy text matching on names/entities.
9. For date() function on bid_closing_date (which is a real DATE column), use date('now') for today.
10. The "fee" column in tenders is in OMR (Omani Rial).

Return a JSON object: {"sql": "<your SELECT statement>", "explanation": "<one line explaining what the query does>"}
"""

# ---------------------------------------------------------------------------
# Tier 1: Deterministic pattern matching
# ---------------------------------------------------------------------------

def _today_iso():
    return date.today().isoformat()


def _match_tier1(question: str):
    """Try to match the question to a known pattern. Returns (sql, explanation, caveats) or None."""
    q = question.strip().lower()

    # --- tenders closing in N days ---
    m = re.search(r"(?:tenders?|opportunities?)\s+(?:closing|due|expiring)\s+(?:in\s+(?:the\s+)?(?:next\s+)?)?(\d+)\s*days?", q)
    if m:
        days = int(m.group(1))
        return (
            f"SELECT t.tender_number, t.tender_name_en, t.entity_en, t.category_en, "
            f"t.grade_en, t.bid_closing_date, t.fee, ts.score, ts.recommendation "
            f"FROM tenders t LEFT JOIN tender_scores ts ON t.tender_number = ts.tender_number "
            f"WHERE t.bid_closing_date BETWEEN date('now') AND date('now', '+{days} days') "
            f"ORDER BY t.bid_closing_date ASC LIMIT {LIMIT_CAP}",
            f"Tenders closing in the next {days} days",
            [],
        )

    # --- tenders scored above X closing in N days ---
    m = re.search(r"(?:tenders?|opportunities?)\s+scored?\s+(?:above|over|>=?)\s*(\d+).*?(?:closing|due)\s+(?:in\s+(?:the\s+)?(?:next\s+)?)?(\d+)\s*days?", q)
    if m:
        score = int(m.group(1))
        days = int(m.group(2))
        return (
            f"SELECT t.tender_number, t.tender_name_en, t.entity_en, t.category_en, "
            f"t.grade_en, t.bid_closing_date, t.fee, ts.score, ts.recommendation "
            f"FROM tenders t JOIN tender_scores ts ON t.tender_number = ts.tender_number "
            f"WHERE ts.score >= {score} AND t.bid_closing_date BETWEEN date('now') AND date('now', '+{days} days') "
            f"ORDER BY ts.score DESC, t.bid_closing_date ASC LIMIT {LIMIT_CAP}",
            f"Tenders scored above {score} closing in the next {days} days",
            [],
        )

    # --- tenders scored above X (no date filter) ---
    m = re.search(r"(?:tenders?|opportunities?)\s+scored?\s+(?:above|over|>=?)\s*(\d+)", q)
    if m:
        score = int(m.group(1))
        return (
            f"SELECT t.tender_number, t.tender_name_en, t.entity_en, t.category_en, "
            f"t.grade_en, t.bid_closing_date, t.fee, ts.score, ts.recommendation "
            f"FROM tenders t JOIN tender_scores ts ON t.tender_number = ts.tender_number "
            f"WHERE ts.score >= {score} "
            f"ORDER BY ts.score DESC LIMIT {LIMIT_CAP}",
            f"Tenders scored above {score}",
            [],
        )

    # --- tenders/awards where <company> bid (in year) ---
    # Matches: "tenders where SCC bid in 2025", "awards where Galfar bid",
    #          "has Premier International bid on any MoT tender above OMR 20M in 2025"
    bid_company = None
    bid_company_display = None

    # Check for SCC / Sarooj first
    if re.search(r"\b(scc|sarooj)\b", q) and "bid" in q:
        bid_company = "SAROOJ"
        bid_company_display = "SCC (Sarooj)"
    else:
        # Check tracked competitors
        for comp in COMPETITORS:
            if comp.lower() in q and ("bid" in q or "tender" in q):
                bid_company = comp
                bid_company_display = comp
                break

    if bid_company:
            # Check for entity filter
            entity_filter = ""
            for ent_kw in ["mot", "ministry of transport", "muscat municipality", "ministry of health",
                           "ministry of education", "ministry of defence"]:
                if ent_kw in q:
                    entity_filter = f" AND at.entity LIKE '%{ent_kw.replace('mot', 'Transport')}%'"
                    break

            # Check for value filter
            value_filter = ""
            m_val = re.search(r"(?:above|over|>=?|more than)\s*(?:omr\s*)?(\d+(?:\.\d+)?)\s*(?:m(?:illion)?|M)", q)
            if m_val:
                val = float(m_val.group(1)) * 1_000_000
                value_filter = f" AND CAST(json_extract(j.value, '$.quoted_value') AS REAL) > {val}"

            # Check for year filter
            year_filter = ""
            m_yr = re.search(r"\b(20\d{2})\b", q)
            if m_yr:
                year_filter = f" AND SUBSTR(at.awarded_date, 7, 4) = '{m_yr.group(1)}'"

            caveats = []
            if bid_company == "SAROOJ":
                caveats.append(CAVEATS["scc_wins"])

            sql = (
                f"SELECT at.tender_number, at.tender_title, at.entity, at.awarded_date, "
                f"at.winner_company, at.winning_value, "
                f"json_extract(j.value, '$.company') AS bidder, "
                f"json_extract(j.value, '$.quoted_value') AS bid_value "
                f"FROM awarded_tenders at, json_each(at.bidders_json) AS j "
                f"WHERE json_extract(j.value, '$.company') LIKE '%{bid_company}%'"
                f"{entity_filter}{year_filter}{value_filter} "
                f"ORDER BY at.awarded_date DESC LIMIT {LIMIT_CAP}"
            )
            return (sql, f"Awarded tenders where {bid_company_display} bid", caveats)

    # --- SCC win rate at <entity> ---
    m = re.search(r"(?:scc|sarooj)(?:'s)?\s+win\s*rate\s+(?:at|for|with)\s+(.+)", q)
    if m:
        entity_raw = m.group(1).strip().rstrip("?.,!")
        entity_like = f"%{entity_raw}%"
        caveats = [CAVEATS["scc_wins"], CAVEATS["win_rate"]]
        if "muscat" in entity_raw.lower() and "municip" in entity_raw.lower():
            caveats.append(CAVEATS["muscat_municipality"])
        # Population = tenders where SCC actually bid (via bidders_json),
        # NOT all awarded tenders at the entity.
        return (
            f"SELECT "
            f"COUNT(DISTINCT at.id) AS scc_bids, "
            f"SUM(CASE WHEN at.winner_company LIKE '%SAROOJ%' THEN 1 ELSE 0 END) AS scc_wins, "
            f"ROUND(100.0 * SUM(CASE WHEN at.winner_company LIKE '%SAROOJ%' THEN 1 ELSE 0 END) "
            f"/ MAX(COUNT(DISTINCT at.id), 1), 1) AS win_rate_pct "
            f"FROM awarded_tenders at, json_each(at.bidders_json) AS j "
            f"WHERE at.entity LIKE '{entity_like}' "
            f"AND json_extract(j.value, '$.company') LIKE '%SAROOJ%' "
            f"LIMIT {LIMIT_CAP}",
            f"SCC win rate at {entity_raw} (bids where SCC participated vs wins)",
            caveats,
        )

    # --- recent awarded tenders by <winner> ---
    m = re.search(r"(?:recent|latest)\s+(?:awarded?\s+)?tenders?\s+(?:by|won by|for)\s+(.+)", q)
    if m:
        winner_raw = m.group(1).strip().rstrip("?.,!")
        return (
            f"SELECT tender_number, tender_title, entity, winner_company, winning_value, "
            f"awarded_date, category, grade "
            f"FROM awarded_tenders "
            f"WHERE winner_company LIKE '%{winner_raw}%' "
            f"ORDER BY awarded_date DESC LIMIT 20",
            f"Recent awarded tenders won by {winner_raw}",
            [],
        )

    # --- who won the most awarded tenders in <year> ---
    m = re.search(r"who\s+won\s+(?:the\s+)?most\s+(?:awarded?\s+)?tenders?\s+(?:in\s+)?(20\d{2})", q)
    if m:
        year = m.group(1)
        return (
            f"SELECT winner_company, COUNT(*) AS wins, "
            f"ROUND(SUM(winning_value), 2) AS total_value "
            f"FROM awarded_tenders "
            f"WHERE SUBSTR(awarded_date, 7, 4) = '{year}' "
            f"AND winner_company IS NOT NULL AND winner_company != '' "
            f"GROUP BY winner_company ORDER BY wins DESC LIMIT 20",
            f"Top winners of awarded tenders in {year}",
            [],
        )

    # --- tenders by category ---
    m = re.search(r"tenders?\s+(?:in|for|under)\s+(?:category\s+)?(?:\")?([a-zA-Z\s&]+)(?:\")?", q)
    if m and "day" not in m.group(1).lower():
        cat = m.group(1).strip()
        return (
            f"SELECT tender_number, tender_name_en, entity_en, category_en, "
            f"grade_en, bid_closing_date, fee "
            f"FROM tenders WHERE category_en LIKE '%{cat}%' "
            f"ORDER BY bid_closing_date DESC LIMIT {LIMIT_CAP}",
            f"Tenders in category matching '{cat}'",
            [],
        )

    # --- tenders by entity/ministry ---
    m = re.search(r"tenders?\s+(?:from|by|at|for)\s+(.+?)(?:\s+(?:above|over|closing|in\s+20)|\?|$)", q)
    if m:
        ent = m.group(1).strip().rstrip("?.,!")
        if len(ent) > 3 and not re.match(r"^\d+$", ent):
            return (
                f"SELECT tender_number, tender_name_en, entity_en, category_en, "
                f"grade_en, bid_closing_date, fee "
                f"FROM tenders WHERE entity_en LIKE '%{ent}%' "
                f"ORDER BY bid_closing_date DESC LIMIT {LIMIT_CAP}",
                f"Tenders from {ent}",
                [],
            )

    # --- news mentioning <keyword> ---
    m = re.search(r"(?:news|articles?)\s+(?:about|mentioning|on|regarding|related to)\s+(.+)", q)
    if m:
        kw = m.group(1).strip().rstrip("?.,!")
        return (
            f"SELECT na.id, na.title, na.source, na.published, na.summary, "
            f"ni.scc_implication, ni.priority "
            f"FROM news_articles na LEFT JOIN news_intelligence ni ON na.id = ni.article_id "
            f"WHERE na.title LIKE '%{kw}%' OR na.summary LIKE '%{kw}%' "
            f"ORDER BY na.published DESC LIMIT 30",
            f"News articles mentioning '{kw}'",
            [],
        )

    # --- show me recent news mentioning <keyword> (alternate phrasing) ---
    m = re.search(r"(?:show|find|get|list)\s+(?:me\s+)?(?:recent\s+)?news\s+(?:about|mentioning|on|regarding)\s+(.+)", q)
    if m:
        kw = m.group(1).strip().rstrip("?.,!")
        return (
            f"SELECT na.id, na.title, na.source, na.published, na.summary, "
            f"ni.scc_implication, ni.priority "
            f"FROM news_articles na LEFT JOIN news_intelligence ni ON na.id = ni.article_id "
            f"WHERE na.title LIKE '%{kw}%' OR na.summary LIKE '%{kw}%' "
            f"ORDER BY na.published DESC LIMIT 30",
            f"Recent news mentioning '{kw}'",
            [],
        )

    return None


# ---------------------------------------------------------------------------
# SQL validation (Tier 2 safety)
# ---------------------------------------------------------------------------

def _validate_sql(sql: str) -> str | None:
    """Validate generated SQL. Returns error message or None if OK."""
    sql_stripped = sql.strip().rstrip(";")

    # 1. Regex-ban dangerous keywords
    if DANGEROUS_KW.search(sql_stripped):
        return f"Blocked: SQL contains dangerous keyword"

    # 2. Check for multiple statements
    # Remove semicolons inside string literals before checking
    no_strings = re.sub(r"'[^']*'", "", sql_stripped)
    if ";" in no_strings:
        return "Blocked: multiple statements detected"

    # 3. Parse with sqlglot AST
    try:
        parsed = sqlglot.parse(sql_stripped, dialect="sqlite")
    except Exception as e:
        return f"Blocked: SQL parse error: {e}"

    if len(parsed) != 1:
        return f"Blocked: expected 1 statement, got {len(parsed)}"

    stmt = parsed[0]
    if stmt is None:
        return "Blocked: empty SQL statement"

    # Must be a SELECT
    if not isinstance(stmt, sqlglot.exp.Select):
        return f"Blocked: not a SELECT statement (got {type(stmt).__name__})"

    # 4. Whitelist tables
    tables_used = set()
    for table in stmt.find_all(sqlglot.exp.Table):
        tname = table.name.lower()
        if tname:
            tables_used.add(tname)

    disallowed = tables_used - ALLOWED_TABLES
    # Allow json_each / json_tree as virtual tables
    disallowed = {t for t in disallowed if t not in ("json_each", "json_tree", "j")}
    if disallowed:
        return f"Blocked: disallowed tables: {disallowed}"

    return None


# ---------------------------------------------------------------------------
# Query execution (read-only, with timeout)
# ---------------------------------------------------------------------------

def _get_db_path() -> str:
    """Extract SQLite file path from DATABASE_URL."""
    url = get_settings().database_url
    # sqlite:///C:/path or sqlite:////abs/path
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    return url


def _execute_readonly(sql: str) -> tuple[list[str], list[list]]:
    """Execute SQL on a read-only SQLite connection. Returns (columns, rows)."""
    db_path = _get_db_path()
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=QUERY_TIMEOUT_S)
    try:
        conn.execute("PRAGMA query_only = ON")
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return columns, rows
    finally:
        conn.close()


def _ensure_limit(sql: str) -> str:
    """Ensure SQL has a LIMIT clause, capped at LIMIT_CAP."""
    upper = sql.upper()
    if "LIMIT" not in upper:
        sql = sql.rstrip().rstrip(";") + f" LIMIT {LIMIT_CAP}"
    else:
        # Check if existing limit exceeds cap
        m = re.search(r"LIMIT\s+(\d+)", upper)
        if m and int(m.group(1)) > LIMIT_CAP:
            sql = re.sub(r"(?i)LIMIT\s+\d+", f"LIMIT {LIMIT_CAP}", sql)
    return sql


# ---------------------------------------------------------------------------
# Tier 2: LLM SQL generation
# ---------------------------------------------------------------------------

def _generate_sql_via_llm(question: str) -> dict | None:
    """Use the existing LLM client to generate SQL from a natural language question."""
    result = call_llm_json(
        system_prompt=SCHEMA_PROMPT,
        user_content=f"Generate a SQLite SELECT query for this question:\n\n{question}",
        temperature=0,
        max_tokens=1024,
    )
    return result


# ---------------------------------------------------------------------------
# Answer narration (anti-hallucination)
# ---------------------------------------------------------------------------

NARRATOR_PROMPT = """You are a data analyst for Sarooj Construction Company (SCC), an Omani civil contractor.
You will receive a user question, the SQL that was executed, and the actual rows returned from the database.

RULES — THESE ARE NON-NEGOTIABLE:
1. ONLY state numbers, names, dates, and values that appear in the provided rows.
2. NEVER invent, estimate, or extrapolate any figure not present in the rows.
3. If zero rows were returned, say "No matching records were found" — do NOT guess an answer.
4. SUMMARISE, do not list every row. State the total count, then highlight the top 3-5 most notable entries. The user can see every row in a collapsible table below your answer — your job is the headline, not the spreadsheet.
5. When showing monetary values, format them in OMR with commas.
6. Present the most important findings first.
7. Do NOT incorporate caveats into your answer — they are shown separately in the UI. Focus only on what the data says.
8. PLAIN TEXT ONLY. Do not use markdown syntax: no **, no ## headings, no bullet points with *. Use plain numbering (1. 2. 3.) and line breaks for structure.

CRITICAL — BID vs WIN distinction:
- The "bidder" column means the company SUBMITTED A BID — it does NOT mean they won.
- The "winner_company" column shows who ACTUALLY WON the tender.
- If the query searched bidders_json, the rows show BID APPEARANCES, not awards/wins.
- A company bidding on a tender and a company winning it are completely different things. Never say "awarded to" or "won by" when describing bid appearances. Say "bid on" or "submitted a bid for".
- To determine if a bidder won, compare bidder to winner_company in the same row.
"""


def _narrate_answer(question: str, sql: str, columns: list[str], rows: list[list],
                     caveats: list[str]) -> str:
    """Use LLM to narrate the query results. Only cites data actually present in rows."""
    if not rows:
        caveat_text = "\n".join(caveats) if caveats else ""
        return f"No matching records were found for this query.{(' ' + caveat_text) if caveat_text else ''}"

    # Feed narrator only the top 10 rows — it summarises the top 3-5 anyway.
    # Full row set is shown in the collapsible UI table.
    display_rows = rows[:10]
    rows_text = json.dumps(
        [dict(zip(columns, row)) for row in display_rows],
        default=str, indent=None
    )
    if len(rows) > 10:
        rows_text += f"\n... ({len(rows)} total rows, showing first 10)"

    user_content = (
        f"QUESTION: {question}\n\n"
        f"SQL EXECUTED: {sql}\n\n"
        f"COLUMNS: {columns}\n\n"
        f"ROWS RETURNED ({len(rows)} total):\n{rows_text}"
    )

    result = call_llm(
        system_prompt=NARRATOR_PROMPT,
        user_content=user_content,
        temperature=0,
        max_tokens=512,
    )
    if result and result.get("text"):
        return result["text"]
    # Fallback: just describe row count
    return f"Query returned {len(rows)} row(s). See the rows in the response for details."


# ---------------------------------------------------------------------------
# Referential / too-vague question detector
# ---------------------------------------------------------------------------

# Pronouns and phrases that reference prior context
_REFERENTIAL_PATTERNS = [
    r"^which\s+ones\b",
    r"^what\s+about\s+(those|them|these|it)\b",
    r"^show\s+(me\s+)?(those|them|these|more|the\s+rest)\b",
    r"^(and|but)\s+(which|what|how|who)\b",
    r"^(list|tell me|give me)\s+(those|them|these)\b",
    r"^(those|them|these|it)\b",
    r"^more\s+(details?|info|about)\b",
    r"^(why|how\s+come|explain)\s+(that|this|it)\b",
]
_REFERENTIAL_RE = [re.compile(p, re.IGNORECASE) for p in _REFERENTIAL_PATTERNS]

# Table/domain nouns that indicate a self-contained question
_DOMAIN_NOUNS = {
    "tender", "tenders", "award", "awarded", "news", "article", "articles",
    "competitor", "competitors", "entity", "entities", "score", "scores",
    "bid", "bids", "scc", "sarooj", "galfar", "strabag", "towell",
    "ministry", "municipality", "category", "grade", "win", "wins",
    "won", "rate", "value", "fee", "construction", "premier",
}


def _detect_referential(question: str) -> str | None:
    """Return a clarification message if the question is too referential to stand alone, else None."""
    q = question.strip()
    q_lower = q.lower().rstrip("?.,!")

    # Check explicit referential patterns
    for pat in _REFERENTIAL_RE:
        if pat.search(q_lower):
            return (
                "I don't have memory of prior questions in this conversation yet. "
                "Could you ask that as a complete question? For example: "
                "'Which tenders did SCC win in 2025?' or 'Show me Galfar's recent bids.'"
            )

    # Very short questions (under 4 words) with no domain noun are likely referential
    words = q_lower.split()
    if len(words) <= 3 and not any(w in _DOMAIN_NOUNS for w in words):
        return (
            "That question is too brief for me to interpret on its own. "
            "Could you rephrase with more detail? For example: "
            "'What tenders are closing this week?' or 'What is SCC's win rate at Muscat Municipality?'"
        )

    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def ask(question: str) -> dict:
    """
    Process a natural-language question.
    Returns: {"answer": str, "sql": str, "rows": list[dict], "tier": 1|2, "caveats": list[str], "error": str|None}
    """
    question = question.strip()
    if not question:
        return {"answer": "Please provide a question.", "sql": "", "rows": [], "tier": 0, "caveats": [], "error": "empty_question"}

    # --- Referential / too-vague check (no conversation memory) ---
    vague = _detect_referential(question)
    if vague:
        return {
            "answer": vague,
            "sql": "",
            "rows": [],
            "tier": 0,
            "caveats": [],
            "error": "referential_question",
        }

    # --- Tier 1: pattern match ---
    tier1 = _match_tier1(question)
    if tier1:
        sql, explanation, caveats = tier1
        sql = _ensure_limit(sql)
        try:
            columns, rows = _execute_readonly(sql)
            rows_dicts = [dict(zip(columns, row)) for row in rows]
            answer = _narrate_answer(question, sql, columns, rows, caveats)
            return {
                "answer": answer,
                "sql": sql,
                "rows": rows_dicts,
                "tier": 1,
                "caveats": caveats,
                "error": None,
            }
        except Exception as e:
            logger.error(f"Tier 1 SQL execution failed: {e}")
            return {
                "answer": f"Query execution failed: {e}",
                "sql": sql,
                "rows": [],
                "tier": 1,
                "caveats": caveats,
                "error": str(e),
            }

    # --- Tier 2: LLM-generated SQL ---
    llm_result = _generate_sql_via_llm(question)
    if not llm_result or "sql" not in llm_result:
        return {
            "answer": "I couldn't generate a query for that question. Try rephrasing with specific table or column names.",
            "sql": "",
            "rows": [],
            "tier": 2,
            "caveats": [],
            "error": "llm_generation_failed",
        }

    sql = llm_result["sql"].strip().rstrip(";")
    explanation = llm_result.get("explanation", "")

    # Validate
    validation_error = _validate_sql(sql)
    if validation_error:
        logger.warning(f"Tier 2 SQL rejected: {validation_error}\nSQL: {sql}")
        return {
            "answer": f"I generated a query but it didn't pass safety checks. Try rephrasing your question.",
            "sql": sql,
            "rows": [],
            "tier": 2,
            "caveats": [],
            "error": validation_error,
        }

    sql = _ensure_limit(sql)

    # Determine caveats
    caveats = []
    q_lower = question.lower()
    if "win rate" in q_lower or "win%" in q_lower:
        caveats.append(CAVEATS["scc_wins"])
        caveats.append(CAVEATS["win_rate"])
    if "muscat" in q_lower and "municip" in q_lower:
        caveats.append(CAVEATS["muscat_municipality"])
    if ("sarooj" in q_lower or "scc" in q_lower) and ("win" in q_lower or "won" in q_lower or "award" in q_lower):
        if CAVEATS["scc_wins"] not in caveats:
            caveats.append(CAVEATS["scc_wins"])

    # Execute
    try:
        columns, rows = _execute_readonly(sql)
        rows_dicts = [dict(zip(columns, row)) for row in rows]
        answer = _narrate_answer(question, sql, columns, rows, caveats)
        return {
            "answer": answer,
            "sql": sql,
            "rows": rows_dicts,
            "tier": 2,
            "caveats": caveats,
            "error": None,
        }
    except Exception as e:
        logger.error(f"Tier 2 SQL execution failed: {e}\nSQL: {sql}")
        return {
            "answer": f"The generated query failed to execute: {e}. Try rephrasing your question.",
            "sql": sql,
            "rows": [],
            "tier": 2,
            "caveats": [],
            "error": str(e),
        }
