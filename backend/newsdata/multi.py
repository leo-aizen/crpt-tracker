"""Composite provider: merges every configured source into one deduped feed.

Cross-source duplicates share no URL, so dedupe falls back to a normalized
headline key. When the same story arrives from both sources, the copy with an
outlet attribution (Google News) wins the slot.
"""
import re
from concurrent.futures import ThreadPoolExecutor

from .base import NewsAdapter
from .curated_rss import CuratedRssAdapter
from .google_news import GoogleNewsAdapter
from .sec_edgar import SecEdgarAdapter
from .yahoo_rss import YahooRssAdapter


def _headline_key(headline):
    return re.sub(r"[^a-z0-9]+", " ", headline.lower()).strip()[:80]


class MultiAdapter(NewsAdapter):
    name = "multi"

    def __init__(self):
        self.providers = [YahooRssAdapter(), GoogleNewsAdapter(),
                          CuratedRssAdapter(), SecEdgarAdapter()]
        self.source_label = ("Yahoo · Google News · WSJ · CNBC · MarketWatch · "
                             "CoinDesk · Cointelegraph · The Block · SEC EDGAR (deduped)")

    def news(self, tickers, names=None):
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda p: self._safe(p, tickers, names), self.providers))
        merged = {}
        for items in results:
            for item in items:
                key = _headline_key(item["headline"])
                prior = merged.get(key)
                if prior is None:
                    merged[key] = item
                else:
                    for t in item["tickers"]:
                        if t not in prior["tickers"]:
                            prior["tickers"].append(t)
                    if item.get("source") and not prior.get("source"):
                        item["tickers"] = prior["tickers"]
                        merged[key] = item
        out = list(merged.values())
        out.sort(key=lambda x: x["published_utc"] or "", reverse=True)
        return out

    @staticmethod
    def _safe(provider, tickers, names):
        try:
            return provider.news(tickers, names)
        except Exception:
            return []  # one source down != feed down
