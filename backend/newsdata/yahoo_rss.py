"""Free real-headline provider: Yahoo Finance per-ticker RSS.

Same unofficial-source family as the marketdata placeholder; swap out via
CRPT_NEWS when a curated provider arrives. Stories that appear under several
holdings are deduped by link with their tickers merged.
"""
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
from email.utils import parsedate_to_datetime

from .base import NewsAdapter

# Our canonical ticker -> Yahoo symbol (this adapter owns its own map).
SYMBOL_MAP = {"3350.JP": "3350.T"}

UA = "Mozilla/5.0 (internal CRPT tracker; contact: SkyBridge research)"
PER_TICKER_LIMIT = 12


def _fetch_rss(ticker: str) -> list[dict]:
    ysym = SYMBOL_MAP.get(ticker, ticker)
    url = (
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s="
        f"{urllib.parse.quote(ysym)}&region=US&lang=en-US"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as resp:
        root = ET.fromstring(resp.read())
    items = []
    for it in list(root.iter("item"))[:PER_TICKER_LIMIT]:
        link = (it.findtext("link") or "").strip()
        title = (it.findtext("title") or "").strip()
        if not link or not title:
            continue
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
            "summary": (it.findtext("description") or "").strip() or None,
            "source": "Yahoo Finance",  # aggregator feed; outlet not attributed
            "url": link,
            "published_utc": published,
        })
    return items


class YahooRssAdapter(NewsAdapter):
    name = "yahoo_rss"
    source_label = "Yahoo Finance RSS (unofficial, per-holding headlines)"

    def news(self, tickers, names=None):
        merged: dict = {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            for result in pool.map(self._safe_fetch, tickers):
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
    def _safe_fetch(ticker):
        try:
            return _fetch_rss(ticker)
        except Exception:
            return []  # absence is the honest answer for that ticker
