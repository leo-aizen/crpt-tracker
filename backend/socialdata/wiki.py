"""Wikipedia attention signal — official Wikimedia pageviews API.

The one attention proxy with an OFFICIAL, open, keyless API (Google Trends
and Reddit are both locked down as of 2026). Used in academic finance as a
retail-attention measure. Momentum = last-7-day average daily article reads
vs the prior ~3-week baseline.

Coverage is partial and honest: only holdings with a real, verified English
Wikipedia article are measured (spot-BTC ETFs and some miners have none).
Article titles below were verified by hand against the live wiki — do not
auto-resolve via search, it mismatches badly (IBIT -> BlackRock).
"""
import json
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

UA = "crpt-tracker internal research tool (contact: leojcbernstein@gmail.com)"

# ticker -> verified article title (None = no dedicated article exists)
ARTICLES = {
    "MSTR": "MicroStrategy",
    "COIN": "Coinbase",
    "3350.JP": None,
    "HOOD": "Robinhood_Markets",
    "ASST": "Strive_Asset_Management",
    "GLXY": "Galaxy_Digital_(company)",
    "IBIT": None, "FBTC": None, "HODL": None, "BITB": None, "BTCO": None,
    "CIFR": None,
    "WULF": "TeraWulf",
    "IREN": "IREN",
    "CLSK": None,
    "RIOT": None,
    "BTDR": "Bitdeer",
    "MARA": "MARA_Holdings",
    "HIVE": None,
}


def _views(article):
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=29)
    url = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
           "en.wikipedia/all-access/user/"
           f"{urllib.parse.quote(article, safe='')}/daily/{start:%Y%m%d}/{end:%Y%m%d}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as resp:
        items = json.load(resp)["items"]
    vals = [i["views"] for i in items]
    if len(vals) < 10:
        return None
    last7 = sum(vals[-7:]) / 7
    base = sum(vals[:-7]) / (len(vals) - 7)
    return {
        "reads_per_day": round(last7),
        "baseline_per_day": round(base),
        "momentum_pct": round((last7 / base - 1) * 100, 1) if base else None,
    }


def attention(tickers):
    """{ticker: {...}} for covered holdings; uncovered are absent."""
    covered = [(t, ARTICLES.get(t)) for t in tickers if ARTICLES.get(t)]

    def safe(pair):
        t, art = pair
        try:
            payload = _views(art)
        except Exception:
            payload = None
        return t, art, payload

    out = {}
    with ThreadPoolExecutor(max_workers=6) as pool:
        for t, art, payload in pool.map(safe, covered):
            if payload is not None:
                out[t] = {"article": art.replace("_", " "), **payload}
    return out
