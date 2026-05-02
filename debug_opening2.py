import hashlib
import requests
from bs4 import BeautifulSoup

BASE = "https://etendering.tenderboard.gov.om"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def opening_report_url(tender_id):
    """Build URL matching the exact pattern from the working browser URL."""
    params = {
        "callAction": "showOpeningStatus_public",
        "strTenderNo": str(tender_id),
        "PublicUrl": "1",
        "CTRL_STRDIRECTION": "LTR",
    }
    # Hash is computed from the VALUES only (concatenated, no randomno value)
    vals = "".join(params.values())  # showOpeningStatus_public + tender_id + 1 + LTR
    hv = hashlib.sha256(vals.encode()).hexdigest()
    
    param_names = list(params.keys()) + ["randomno"]
    encparam = ",".join(param_names)
    
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{BASE}/product/tmsbidopen/TenderOpeningQCRStatusAction.action?{qs}&encparam={encparam}&hashval={hv}"


s = requests.Session()
s.headers.update(HEADERS)

# Warmup
s.get(f"{BASE}/product/publicDash?viewFlag=NewTenders&CTRL_STRDIRECTION=LTR", timeout=30)

# Test with known tender
for tid in ["84025", "83780", "83138"]:
    url = opening_report_url(tid)
    print(f"\nTender ID: {tid}")
    print(f"URL: {url[:120]}...")
    
    r = s.get(url, timeout=30)
    soup = BeautifulSoup(r.content, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else "No title"
    print(f"Title: {title}")
    
    if "error" in title.lower() or "security" in title.lower():
        print("BLOCKED — trying alternative hash...")
        # Try with randomno in the values
        params2 = {
            "callAction": "showOpeningStatus_public",
            "strTenderNo": str(tid),
            "PublicUrl": "1",
            "CTRL_STRDIRECTION": "LTR",
            "randomno": "",
        }
        vals2 = "".join(v for v in params2.values() if v)
        hv2 = hashlib.sha256(vals2.encode()).hexdigest()
        encparam2 = ",".join(params2.keys())
        qs2 = "&".join(f"{k}={v}" for k, v in params2.items() if v)
        url2 = f"{BASE}/product/tmsbidopen/TenderOpeningQCRStatusAction.action?{qs2}&encparam={encparam2}&hashval={hv2}"
        
        r = s.get(url2, timeout=30)
        soup = BeautifulSoup(r.content, "html.parser")
        title = soup.title.get_text(strip=True) if soup.title else "No title"
        print(f"Alt title: {title}")
    
    # Parse if we got through
    if "error" not in title.lower() and "security" not in title.lower():
        tables = soup.find_all("table")
        for t in tables:
            rows = t.find_all("tr")
            if len(rows) > 2:
                print(f"Table with {len(rows)} rows:")
                for row in rows[:5]:
                    cells = row.find_all(["td", "th"])
                    texts = [c.get_text(strip=True)[:50] for c in cells]
                    print(f"  {texts}")
