"""Stocktwits public symbol streams — free, keyless, finance-native.

Cashtag streams sidestep the ticker-ambiguity problem entirely ("$RIOT" is
the miner, never the game studio). The post rate is ESTIMATED from the
newest 30 messages' timespan and labeled as such in the UI. Tokyo-listed
Metaplanet is not on Stocktwits; its absence renders as "no data".
"""
import json
import re
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .base import SocialAdapter

UA = "Mozilla/5.0 (internal CRPT tracker; contact: SkyBridge research)"

# Our canonical ticker -> Stocktwits symbol. None = known-uncovered.
SYMBOL_MAP = {"3350.JP": None}


def _parse_ts(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return None


_TAG_RX = re.compile(r"\$[A-Za-z0-9.]+")
_URL_RX = re.compile(r"https?://\S+")


def _substantive(body: str) -> bool:
    """Keep posts with actual words; drop tag-walls, link dumps, emoji spam."""
    if len(_TAG_RX.findall(body)) > 6:
        return False
    stripped = _URL_RX.sub("", _TAG_RX.sub("", body))
    letters = sum(1 for ch in stripped if ch.isalpha())
    return letters >= 20


def _fetch_symbol(our_sym):
    st_sym = SYMBOL_MAP.get(our_sym, our_sym)
    if st_sym is None:
        return our_sym, None
    url = f"https://api.stocktwits.com/api/2/streams/symbol/{urllib.parse.quote(st_sym)}.json"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.load(resp)
    msgs = data.get("messages") or []
    posts, stamps, seen_bodies = [], [], set()
    for m in msgs:
        ts = _parse_ts(m.get("created_at") or "")
        if ts:
            stamps.append(ts)  # rate uses ALL messages — spam is still activity
        body = (m.get("body") or "").strip()
        norm = " ".join(body.lower().split())[:60]
        if not _substantive(body) or norm in seen_bodies:
            continue  # the readable stream is filtered for substance
        seen_bodies.add(norm)
        user = (m.get("user") or {}).get("username") or "unknown"
        posts.append({
            "id": m.get("id"),
            "body": body,
            "user": user,
            "likes": (m.get("likes") or {}).get("total", 0),
            "created_utc": ts.isoformat(timespec="seconds") if ts else None,
            "url": f"https://stocktwits.com/{user}/message/{m.get('id')}",
        })
    rate = None
    if len(stamps) >= 2:
        span_days = max((max(stamps) - min(stamps)).total_seconds() / 86400, 1 / 96)
        rate = round((len(stamps) - 1) / span_days, 1)
    return our_sym, {
        "watchers": (data.get("symbol") or {}).get("watchlist_count"),
        "post_rate_per_day": rate,
        "sample_size": len(msgs),
        "posts": posts,
    }


class StocktwitsAdapter(SocialAdapter):
    name = "stocktwits"
    source_label = "Stocktwits public streams (free, keyless)"

    def activity(self, symbols):
        out = {}
        with ThreadPoolExecutor(max_workers=6) as pool:
            for sym, payload in pool.map(self._safe, symbols):
                if payload is not None:
                    out[sym] = payload
        return out

    @staticmethod
    def _safe(sym):
        try:
            return _fetch_symbol(sym)
        except Exception:
            return sym, None  # absence == honest "no data"
