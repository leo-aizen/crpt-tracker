"""Curated vetted-outlet feeds: WSJ, CNBC, MarketWatch, CoinDesk,
Cointelegraph, The Block — established newsrooms an SEC-registered firm can
cite. These are firehose feeds, so items are kept only when the headline or
description clearly references one of our holdings (company name, or the
ticker as an exact uppercase token — "$RIOT"/"RIOT", never "riot police").
"""
import re
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
from email.utils import parsedate_to_datetime

from .base import NewsAdapter

UA = "Mozilla/5.0 (internal CRPT tracker; contact: SkyBridge research)"

OUTLETS = [
    ("WSJ Markets", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("CNBC", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "https://cointelegraph.com/rss"),
    ("The Block", "https://www.theblock.co/rss.xml"),
]

# Per-holding match terms: case-insensitive name phrases + case-sensitive
# ticker tokens (uppercase word match keeps "HOOD the stock", drops "hoodie").
MATCH_TERMS = {
    "MSTR": (["MicroStrategy", "Michael Saylor"], ["MSTR"]),
    "COIN": (["Coinbase"], ["COIN"]),
    "3350.JP": (["Metaplanet"], []),
    "HOOD": (["Robinhood"], ["HOOD"]),
    "ASST": (["Strive"], ["ASST"]),
    "GLXY": (["Galaxy Digital"], ["GLXY"]),
    "IBIT": (["iShares Bitcoin"], ["IBIT"]),
    "FBTC": (["Fidelity Wise Origin"], ["FBTC"]),
    "HODL": (["VanEck Bitcoin"], []),  # bare "HODL" is crypto slang — name only
    "BITB": (["Bitwise Bitcoin"], ["BITB"]),
    "BTCO": (["Invesco Galaxy Bitcoin"], ["BTCO"]),
    "CIFR": (["Cipher Mining", "Cipher Digital"], ["CIFR"]),
    "WULF": (["TeraWulf"], ["WULF"]),
    "IREN": (["Iris Energy"], ["IREN"]),
    "CLSK": (["CleanSpark"], ["CLSK"]),
    "RIOT": (["Riot Platforms"], ["RIOT"]),
    "BTDR": (["Bitdeer"], ["BTDR"]),
    "MARA": (["MARA Holdings", "Marathon Digital"], ["MARA"]),
    "HIVE": (["HIVE Digital"], ["HIVE"]),
}


def _matchers(tickers):
    out = []
    for t in tickers:
        names, toks = MATCH_TERMS.get(t, ([], [t] if t.isupper() and t.isalpha() else []))
        pats = [re.compile(re.escape(n), re.I) for n in names]
        pats += [re.compile(rf"(?<![A-Z$]){re.escape(tok)}(?![A-Z])") for tok in toks]
        out.append((t, pats))
    return out


def _fetch_outlet(outlet):
    name, url = outlet
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as resp:
        root = ET.fromstring(resp.read())
    items = []
    for it in list(root.iter("item"))[:60]:
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if not title or not link:
            continue
        desc = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")[:400].strip()
        published = None
        raw = it.findtext("pubDate")
        if raw:
            try:
                published = parsedate_to_datetime(raw).astimezone(timezone.utc).isoformat(timespec="seconds")
            except Exception:
                published = None
        items.append({"outlet": name, "title": title, "link": link,
                      "desc": desc, "published": published})
    return items


class CuratedRssAdapter(NewsAdapter):
    name = "curated_rss"
    source_label = "WSJ / CNBC / MarketWatch / CoinDesk / Cointelegraph / The Block"

    def news(self, tickers, names=None):
        matchers = _matchers(tickers)
        with ThreadPoolExecutor(max_workers=6) as pool:
            raw = [i for items in pool.map(self._safe, OUTLETS) for i in items]
        out = []
        for it in raw:
            text = f"{it['title']} {it['desc']}"
            hit = [t for t, pats in matchers if any(p.search(text) for p in pats)]
            if not hit:
                continue
            out.append({
                "id": it["link"],
                "tickers": hit,
                "headline": it["title"],
                "summary": it["desc"] or None,
                "source": it["outlet"],
                "url": it["link"],
                "published_utc": it["published"],
            })
        out.sort(key=lambda x: x["published_utc"] or "", reverse=True)
        return out

    @staticmethod
    def _safe(outlet):
        try:
            return _fetch_outlet(outlet)
        except Exception:
            return []
