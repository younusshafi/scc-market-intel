import hashlib
import requests
from bs4 import BeautifulSoup

BASE = "https://etendering.tenderboard.gov.om"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def opening_report_url(tender_id):
    params = {
        "callAction": "showOpeningStatus_public",
        "strTenderNo": tender_id,
        "PublicUrl": "1",
    }
    full = dict(params)
    full["CTRL_STRDIRECTION"] = "LTR"
    full["randomno"] = "fixedrandomno"
    names = ",".join(full.keys())
    vals = "".join(v for v in full.values() if v)
    hv = hashlib.sha256(vals.encode()).hexdigest()
    qs = "&".join(f"{k}={v}" for k, v in full.items())
    return f"{BASE}/product/tmsbidopen/TenderOpeningQCRStatusAction.action?{qs}&encparam={names}&hashval={hv}"


s = requests.Session()
s.headers.update(HEADERS)

# Test with a known awarded tender that has 9 bidders
tid = "84025"
url = opening_report_url(tid)
print(f"URL: {url[:100]}...")

r = s.get(url, timeout=30)
soup = BeautifulSoup(r.content, "html.parser")
title = soup.title.get_text(strip=True) if soup.title else "No title"
print(f"Title: {title}")
print(f"Status: {r.status_code}")
print(f"Content length: {len(r.content)}")

# Show ALL tables
tables = soup.find_all("table")
print(f"\nTables found: {len(tables)}")

for i, table in enumerate(tables):
    rows = table.find_all("tr")
    print(f"\n--- Table {i} ({len(rows)} rows) ---")
    for j, row in enumerate(rows[:12]):
        cells = row.find_all(["td", "th"])
        texts = [c.get_text(strip=True)[:50] for c in cells]
        print(f"  Row {j}: {texts}")

# Also dump a chunk of raw HTML to see structure
print("\n--- RAW HTML snippet (first 3000 chars of body) ---")
body = soup.find("body")
if body:
    print(str(body)[:3000])
