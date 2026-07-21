"""SEC EDGAR filings per holding — the most defensible source there is:
the companies' own filings, straight from the regulator.

Routine insider forms (3/4/5, 144) are excluded so the feed carries the
filings a desk actually reads: 8-K, 10-Q/K, S-1/S-3, prospectuses, 13D/G,
6-K. Tokyo-listed Metaplanet doesn't file with the SEC — honestly absent.
SEC asks automated clients to identify themselves in the User-Agent.
"""
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

from .base import NewsAdapter

UA = "SkyBridge CRPT tracker (internal research; contact leojcbernstein@gmail.com)"
ATOM = "{http://www.w3.org/2005/Atom}"
SKIP_TYPES = {"3", "4", "5", "3/A", "4/A", "5/A", "144", "144/A"}
PER_TICKER_LIMIT = 4


def _fetch_filings(ticker, names):
    url = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
           f"&CIK={urllib.parse.quote(ticker)}&type=&count=20&output=atom")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as resp:
        root = ET.fromstring(resp.read())
    company = (names or {}).get(ticker) or ticker
    items = []
    for e in root.iter(f"{ATOM}entry"):
        title = (e.findtext(f"{ATOM}title") or "").strip()
        # titles look like "8-K  - Current report": type, padded dash, label
        ftype = re.split(r"\s+-\s+", title, maxsplit=1)[0].strip()
        if ftype in SKIP_TYPES:
            continue
        link_el = e.find(f"{ATOM}link")
        link = link_el.get("href") if link_el is not None else None
        updated = (e.findtext(f"{ATOM}updated") or "").strip() or None
        if not link:
            continue
        items.append({
            "id": link,
            "tickers": [ticker],
            "headline": f"{company}: SEC filing {title}",
            "summary": None,
            "source": "SEC EDGAR",
            "url": link,
            "published_utc": updated,
        })
        if len(items) >= PER_TICKER_LIMIT:
            break
    return items


class SecEdgarAdapter(NewsAdapter):
    name = "sec_edgar"
    source_label = "SEC EDGAR filings"

    def news(self, tickers, names=None):
        us = [t for t in tickers if not t.endswith(".JP")]
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = pool.map(lambda t: self._safe(t, names), us)
        out = [i for items in results for i in items]
        out.sort(key=lambda x: x["published_utc"] or "", reverse=True)
        return out

    @staticmethod
    def _safe(ticker, names):
        try:
            return _fetch_filings(ticker, names)
        except Exception:
            return []
