"""Google News RSS provider — aggregates headlines from many outlets
(Reuters, Bloomberg, CNBC, CoinDesk, ...) per holding, free and keyless.

Queries pair the ticker with the company name to cut ticker-collision noise
("HOOD the stock", not the neighborhood). The item's <source> tag attributes
the actual outlet, which the UI displays.
"""
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
from email.utils import parsedate_to_datetime

from .base import NewsAdapter

UA = "Mozilla/5.0 (internal CRPT tracker; contact: SkyBridge research)"
PER_TICKER_LIMIT = 10

# Company-name hints for tickers whose bare symbol is a common word.
NAME_HINTS = {"3350.JP": "Metaplanet", "HODL": "VanEck Bitcoin ETF", "HIVE": "HIVE Digital"}


def _query_for(ticker, names):
    name = NAME_HINTS.get(ticker) or (names or {}).get(ticker) or ""
    # strip share-class suffixes etc. down to the lead words of the name
    name = " ".join(name.replace("(Class A)", "").replace(",", "").split()[:2])
    return f'"{ticker}" {name}'.strip() if name else f'"{ticker}" stock'


def _fetch_rss(ticker, names):
    q = urllib.parse.quote(_query_for(ticker, names))
    url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as resp:
        root = ET.fromstring(resp.read())
    items = []
    for it in list(root.iter("item"))[:PER_TICKER_LIMIT]:
        link = (it.findtext("link") or "").strip()
        title = (it.findtext("title") or "").strip()
        if not link or not title:
            continue
        source = (it.findtext("source") or "").strip() or None
        # Google formats titles as "Headline - Outlet"; drop the duplicate tail
        if source and title.endswith(f"- {source}"):
            title = title[: -len(source) - 2].rstrip()
        published = None
        raw = it.findtext("pubDate")
        if raw:
            try:
                published = parsedate_to_datetime(raw).astimezone(timezone.utc).isoformat(timespec="seconds")
            except Exception:
                published = None
        items.append({
            "id": it.findtext("guid") or link,
            "tickers": [ticker],
            "headline": title,
            "summary": None,  # Google News descriptions are just links; omit
            "source": source,
            "url": link,
            "published_utc": published,
        })
    return items


class GoogleNewsAdapter(NewsAdapter):
    name = "google_news"
    source_label = "Google News RSS (multi-outlet headlines)"

    def news(self, tickers, names=None):
        merged = {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            for result in pool.map(lambda t: self._safe(t, names), tickers):
                for item in result:
                    key = item["url"]
                    if key in merged:
                        prior = merged[key]["tickers"]
                        prior.extend(t for t in item["tickers"] if t not in prior)
                    else:
                        merged[key] = item
        out = list(merged.values())
        out.sort(key=lambda x: x["published_utc"] or "", reverse=True)
        return out

    @staticmethod
    def _safe(ticker, names):
        try:
            return _fetch_rss(ticker, names)
        except Exception:
            return []
