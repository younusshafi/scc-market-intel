"""
Session probe for etendering.tenderboard.gov.om

Investigates whether tender listing pages require actual login credentials
or just need a properly established session (cookies + CSRF token).

Strategy:
  1. GET the main dashboard in a requests.Session — capture cookies + ran token
  2. Replay that session with POSTs to tender listing endpoints
  3. Also try GETs, partial form data, and alternative endpoints
  4. Save every response to a separate HTML file for manual inspection
  5. Classify each response: tender data / security wall / redirect / error
"""

import json
import os
import re
import sys
import traceback
from collections import OrderedDict

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests
from bs4 import BeautifulSoup

BASE = "https://etendering.tenderboard.gov.om"
OUT_DIR = "probe_responses"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_out_dir():
    os.makedirs(OUT_DIR, exist_ok=True)


def save(name, resp):
    """Save response body and return the file path."""
    path = os.path.join(OUT_DIR, name)
    with open(path, "wb") as f:
        f.write(resp.content)
    return path


def classify(resp):
    """Classify a response as one of: TENDER_DATA, SECURITY_WALL, DASHBOARD, ERROR, UNKNOWN."""
    if resp.status_code != 200:
        return f"HTTP_{resp.status_code}"

    text = resp.text[:5000].lower()

    if "security page" in text or "session in the client area has expired" in text:
        return "SECURITY_WALL"
    if "unable to access the requested page" in text:
        return "SECURITY_WALL"
    # Check for a tender listing table — look for tender-number-like patterns
    # or table headers that suggest tender data
    if re.search(r'<table.*?class.*?tender', text, re.I):
        return "TENDER_DATA"
    if re.search(r'tender\s*no|مناقصة\s*رقم|tender\s*number', text, re.I):
        return "TENDER_DATA"
    if "viewflag" in text and "<table" in text:
        return "TENDER_DATA"
    # If it has many table rows, it might be a listing
    if text.count("<tr") > 10:
        return "POSSIBLE_DATA"
    if "publicdash" in text and "chartdiv" in text:
        return "DASHBOARD"
    if len(resp.content) < 500:
        return "EMPTY_OR_MINIMAL"

    return "UNKNOWN"


def extract_form_fields(soup):
    """Extract all hidden fields from the bDashboard form."""
    fields = OrderedDict()
    form = soup.find("form", attrs={"name": "bDashboard"})
    if not form:
        form = soup.find("form")
    if form:
        for inp in form.find_all("input"):
            name = inp.get("name")
            if name:
                fields[name] = inp.get("value", "")
    return fields


def report(tag, resp, filename):
    """Print a one-line summary of a probe result."""
    kind = classify(resp)
    size = len(resp.content)
    ct = resp.headers.get("Content-Type", "")[:40]
    url = resp.url

    # Count table rows as a signal
    row_count = resp.text.lower().count("<tr")

    indicator = {
        "TENDER_DATA": "*** TENDER DATA FOUND ***",
        "POSSIBLE_DATA": "~~~ possible data ~~~",
        "SECURITY_WALL": "BLOCKED (login required)",
        "DASHBOARD": "dashboard (no tender list)",
        "EMPTY_OR_MINIMAL": "empty/minimal response",
    }.get(kind, kind)

    print(f"  [{tag:12s}] {resp.status_code} | {size:>8,}b | {row_count:>3} <tr> | {indicator}")
    print(f"               {url}")
    print(f"               -> {filename}")
    return kind


def section(title):
    print(f"\n{'='*72}")
    print(f"  {title}")
    print(f"{'='*72}")


# ---------------------------------------------------------------------------
# Probes
# ---------------------------------------------------------------------------

def main():
    ensure_out_dir()
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)
    results = {}

    # ==================================================================
    # PHASE 1: Establish session — GET the main dashboard
    # ==================================================================
    section("PHASE 1: Establish session via GET /product/publicDash")

    r = session.get(BASE, timeout=30)
    save("01_initial_get.html", r)
    print(f"  Status: {r.status_code} | Final URL: {r.url}")
    print(f"  Size: {len(r.content):,} bytes")

    # Show cookies received
    print(f"\n  Cookies received:")
    for c in session.cookies:
        print(f"    {c.name} = {c.value[:40]}{'...' if len(c.value) > 40 else ''}")
        print(f"      domain={c.domain}  path={c.path}  secure={c.secure}")

    # Extract form fields + ran token
    soup = BeautifulSoup(r.content, "html.parser")
    form_fields = extract_form_fields(soup)
    ran_token = form_fields.get("ran", "")

    print(f"\n  Form fields extracted: {len(form_fields)}")
    print(f"  ran token: {ran_token!r}")
    print(f"\n  All hidden field names + values:")
    for name, val in form_fields.items():
        if val:
            print(f"    {name:25s} = {val!r}")
        else:
            print(f"    {name:25s} = (empty)")

    # ==================================================================
    # PHASE 2: POST tender listing endpoints with session cookies
    # ==================================================================
    section("PHASE 2: POST to tender endpoints (with session)")

    # Build the minimal form payload that mirrors what submitPage() sends
    base_payload = {
        "securityFlag": "1",
        "PublicUrl": "1",
        "CTRL_STRDIRECTION": "RTL",
        "ran": ran_token,
        "NEW": "1",
    }

    # Also build a "full" payload with all form fields
    full_payload = dict(form_fields)

    post_targets = [
        ("NewTenders",      f"{BASE}/product/publicDash",                 {"viewFlag": "NewTenders"}),
        ("InProcess",       f"{BASE}/product/publicDash",                 {"viewFlag": "InProcessTenders"}),
        ("SubContract",     f"{BASE}/product/publicDash",                 {"viewFlag": "SubContractTenders", "statusFlag": "NewTenders"}),
        ("Completed",       f"{BASE}/product/CompletedTendersForPublic",  {}),
        ("Canceled",        f"{BASE}/product/CanceledTendersForPublic",   {}),
    ]

    # 2a: POST with minimal payload
    print("\n  --- 2a: POST with minimal payload (base fields only) ---")
    for tag, url, extra in post_targets:
        payload = {**base_payload, **extra}
        r = session.post(url, data=payload, timeout=30)
        fname = save(f"02a_post_minimal_{tag}.html", r)
        results[f"post_minimal_{tag}"] = report(tag, r, fname)

    # 2b: POST with full payload (all form fields)
    print("\n  --- 2b: POST with full form payload (all fields) ---")
    for tag, url, extra in post_targets:
        payload = {**full_payload, **extra}
        r = session.post(url, data=payload, timeout=30)
        fname = save(f"02b_post_full_{tag}.html", r)
        results[f"post_full_{tag}"] = report(tag, r, fname)

    # 2c: POST with Referer header set (some servers check this)
    print("\n  --- 2c: POST with Referer header ---")
    session.headers["Referer"] = f"{BASE}/product/publicDash"
    session.headers["Origin"] = BASE
    for tag, url, extra in post_targets[:2]:  # just NewTenders + InProcess
        payload = {**full_payload, **extra}
        r = session.post(url, data=payload, timeout=30)
        fname = save(f"02c_post_referer_{tag}.html", r)
        results[f"post_referer_{tag}"] = report(tag, r, fname)

    # ==================================================================
    # PHASE 3: GET requests (no form POST)
    # ==================================================================
    section("PHASE 3: GET requests (query params only, no POST body)")

    get_targets = [
        ("NewTenders_GET",    f"{BASE}/product/publicDash?viewFlag=NewTenders"),
        ("InProcess_GET",     f"{BASE}/product/publicDash?viewFlag=InProcessTenders"),
        ("SubContr_GET",      f"{BASE}/product/publicDash?viewFlag=SubContractTenders&statusFlag=NewTenders"),
        ("Completed_GET",     f"{BASE}/product/CompletedTendersForPublic"),
        ("Canceled_GET",      f"{BASE}/product/CanceledTendersForPublic"),
        ("Vacancy_GET",       f"{BASE}/product/publicDash?viewFlag=vacancyList&pageView=P&direct=RTL&siteUrl=etendering.tenderboard.gov.om"),
        ("SiteMap_GET",       f"{BASE}/product/publicDash?viewFlag=ViewSiteMap"),
        ("ReportVndr_GET",    f"{BASE}/product/ReportAction?eventFlag=RegVendorPublic"),
    ]

    for tag, url in get_targets:
        r = session.get(url, timeout=30)
        fname = save(f"03_get_{tag}.html", r)
        results[f"get_{tag}"] = report(tag, r, fname)

    # ==================================================================
    # PHASE 4: Probe the only known AJAX endpoint with different params
    # ==================================================================
    section("PHASE 4: Probe /product/ajaxMasterUpdate with different callvalue params")

    ajax_url = f"{BASE}/product/ajaxMasterUpdate"
    callvalues = [
        "GetClockTime",
        "GetTenders",
        "GetNewTenders",
        "GetPublicTenders",
        "TenderList",
        "SearchTender",
        "GetAllTenders",
        "NewTenders",
        "PublicDash",
        "GetFloatedTenders",
    ]

    for cv in callvalues:
        try:
            r = session.get(ajax_url, params={"callvalue": cv, "CTRL_Direction": "RTL"}, timeout=15)
            size = len(r.content)
            ct = r.headers.get("Content-Type", "")[:40]
            text_preview = r.text[:200].replace("\n", " ").replace("\r", "")
            print(f"  callvalue={cv:25s} -> {r.status_code} | {size:>6}b | {ct:30s} | {text_preview[:60]}")
            if size > 100:
                save(f"04_ajax_{cv}.txt", r)
        except Exception as e:
            print(f"  callvalue={cv:25s} -> ERROR: {e}")

    # ==================================================================
    # PHASE 5: Probe hidden/commented-out endpoints
    # ==================================================================
    section("PHASE 5: Probe hidden/alternative endpoints")

    hidden_targets = [
        ("buyerDash",          f"{BASE}/product/buyerDash?PublicUrl=1"),
        ("buyerDash_aa",       f"{BASE}/product/buyerDash?PublicUrl=1&aa=2"),
        ("FAQ_tenderStatic",   f"{BASE}/product/DefineFAQ?aa=2&callValue=tenderStatic"),
        ("FAQ_view",           f"{BASE}/product/DefineFAQ?callValue=view"),
        ("ShowNews",           f"{BASE}/product/ShowNews?ShowNews=GetNews"),
        ("TrainingKits_1",     f"{BASE}/product/trainingKits/TrainingKitDocUploadActionPub.action?DocTypeId=1"),
        ("TrainingKits_2",     f"{BASE}/product/trainingKits/TrainingKitDocUploadActionPub.action?DocTypeId=2"),
        ("TrainingKits_5",     f"{BASE}/product/trainingKits/TrainingKitDocUploadActionPub.action?DocTypeId=5"),
        ("WebCast",            f"{BASE}/product/webcast/WebCastActionPub.action?viewWCFlag=pdashboard"),
        ("usefulsites_jsp",    f"{BASE}/product/jsp/dashboards/usefulsites.jsp"),
        ("abc_htm",            f"{BASE}/product/jsp/dashboards/abc.htm"),
    ]

    # Try as GET first
    print("\n  --- 5a: GET requests ---")
    for tag, url in hidden_targets:
        try:
            r = session.get(url, timeout=15)
            fname = save(f"05a_get_{tag}.html", r)
            results[f"hidden_get_{tag}"] = report(tag, r, fname)
        except Exception as e:
            print(f"  [{tag:12s}] ERROR: {e}")

    # Try POST for buyerDash and FAQ
    print("\n  --- 5b: POST with full form payload ---")
    for tag, url in hidden_targets[:4]:
        try:
            r = session.post(url, data=full_payload, timeout=15)
            fname = save(f"05b_post_{tag}.html", r)
            results[f"hidden_post_{tag}"] = report(tag, r, fname)
        except Exception as e:
            print(f"  [{tag:12s}] ERROR: {e}")

    # ==================================================================
    # PHASE 6: Try English (LTR) dashboard with session
    # ==================================================================
    section("PHASE 6: English (LTR) dashboard via POST")

    ltr_payload = {**full_payload, "CTRL_STRDIRECTION": "LTR"}
    r = session.post(f"{BASE}/product/publicDash", data=ltr_payload, timeout=30)
    fname = save("06_post_ltr_dashboard.html", r)
    results["ltr_dashboard"] = report("LTR_Dash", r, fname)

    # If it succeeded, check for English tender listings
    if classify(r) != "SECURITY_WALL":
        ltr_soup = BeautifulSoup(r.content, "html.parser")
        ltr_fields = extract_form_fields(ltr_soup)
        ltr_ran = ltr_fields.get("ran", ran_token)

        for tag, url, extra in post_targets[:2]:
            payload = {**ltr_fields, **extra, "CTRL_STRDIRECTION": "LTR"}
            r = session.post(url, data=payload, timeout=30)
            fname = save(f"06_post_ltr_{tag}.html", r)
            results[f"ltr_{tag}"] = report(f"LTR_{tag}", r, fname)

    # ==================================================================
    # PHASE 7: Deep inspect any non-SECURITY_WALL responses
    # ==================================================================
    section("PHASE 7: Detailed inspection of promising responses")

    # Re-read all saved HTML files and look for table structures
    for fname in sorted(os.listdir(OUT_DIR)):
        if not fname.endswith(".html"):
            continue
        fpath = os.path.join(OUT_DIR, fname)
        with open(fpath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        soup = BeautifulSoup(content, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else "(no title)"
        tables = soup.find_all("table")
        forms = soup.find_all("form")
        tr_count = len(soup.find_all("tr"))
        size = len(content)

        # Only report interesting ones (not security walls, not the main dashboard)
        if "security page" in title.lower():
            continue
        if size < 1000:
            continue

        has_tender_kw = bool(re.search(
            r'tender.?no|tender.?number|مناقصة|رقم المناقصة|bid|عطاء',
            content[:20000], re.I
        ))

        if tables or has_tender_kw or tr_count > 5:
            print(f"\n  {fname}")
            print(f"    Title: {title[:80]}")
            print(f"    Size: {size:,} | Tables: {len(tables)} | <tr>: {tr_count} | Forms: {len(forms)}")
            print(f"    Tender keywords: {has_tender_kw}")

            for idx, table in enumerate(tables):
                rows = table.find_all("tr")
                if rows:
                    headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
                    print(f"    Table {idx}: {len(rows)} rows, headers: {headers[:8]}")
                    if len(rows) > 1:
                        sample = [td.get_text(strip=True)[:30] for td in rows[1].find_all("td")]
                        print(f"      Sample row: {sample[:8]}")

    # ==================================================================
    # SUMMARY
    # ==================================================================
    section("FINAL SUMMARY")

    blocked = [k for k, v in results.items() if v == "SECURITY_WALL"]
    got_data = [k for k, v in results.items() if v in ("TENDER_DATA", "POSSIBLE_DATA")]
    other = [k for k, v in results.items() if v not in ("SECURITY_WALL", "TENDER_DATA", "POSSIBLE_DATA")]

    print(f"\n  Total probes:     {len(results)}")
    print(f"  Got tender data:  {len(got_data)}")
    print(f"  Blocked (login):  {len(blocked)}")
    print(f"  Other:            {len(other)}")

    if got_data:
        print(f"\n  *** ENDPOINTS THAT RETURNED DATA: ***")
        for k in got_data:
            print(f"    {k}")

    if blocked:
        print(f"\n  Endpoints that hit the login wall:")
        for k in blocked:
            print(f"    {k}")

    if other:
        print(f"\n  Other responses:")
        for k in other:
            print(f"    {k:40s} -> {results[k]}")

    # Save summary
    with open(os.path.join(OUT_DIR, "probe_summary.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Results saved to {OUT_DIR}/probe_summary.json")
    print(f"  All response HTML saved to {OUT_DIR}/")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
