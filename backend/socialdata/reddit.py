"""Reddit adapter — READY BUT DORMANT until API credentials exist.

Reddit closed keyless JSON access, so this adapter needs a (free) registered
app: create one at reddit.com/prefs/apps (type: "script"), then export
  CRPT_REDDIT_CLIENT_ID / CRPT_REDDIT_CLIENT_SECRET
and set CRPT_SOCIAL=reddit. Without credentials it raises at startup with
that exact instruction rather than pretending to work.

Searches finance subreddits per holding (cashtag + company name) over the
past week — the same activity contract as the Stocktwits adapter, so the
heatmap works identically. NOTE: written against Reddit's documented OAuth
client-credentials flow but untested until real credentials are supplied.
"""
import base64
import json
import os
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from .base import SocialAdapter

UA = "macos:crpt-tracker:v0.10 (internal research; contact leojcbernstein@gmail.com)"
SUBS = "wallstreetbets+stocks+investing+CryptoCurrency+Bitcoin+BitcoinMiners"

QUERY_HINTS = {
    "3350.JP": '"Metaplanet"',
    "HODL": '"VanEck" OR "$HODL"',   # bare HODL is slang, not the ETF
    "HIVE": '"HIVE Digital" OR "$HIVE"',
    "COIN": '"Coinbase" OR "$COIN"',
    "HOOD": '"Robinhood" OR "$HOOD"',
    "RIOT": '"Riot Platforms" OR "$RIOT"',
}


class RedditAdapter(SocialAdapter):
    name = "reddit"
    source_label = "Reddit finance subreddits (official API)"

    def __init__(self):
        self.client_id = os.environ.get("CRPT_REDDIT_CLIENT_ID")
        self.secret = os.environ.get("CRPT_REDDIT_CLIENT_SECRET")
        if not self.client_id or not self.secret:
            raise RuntimeError(
                "Reddit adapter needs credentials: create a free 'script' app at "
                "reddit.com/prefs/apps, then set CRPT_REDDIT_CLIENT_ID and "
                "CRPT_REDDIT_CLIENT_SECRET (or use CRPT_SOCIAL=stocktwits)."
            )
        self._token = None
        self._token_exp = 0.0

    def _access_token(self):
        if self._token and time.monotonic() < self._token_exp - 60:
            return self._token
        auth = base64.b64encode(f"{self.client_id}:{self.secret}".encode()).decode()
        req = urllib.request.Request(
            "https://www.reddit.com/api/v1/access_token",
            data=b"grant_type=client_credentials",
            headers={"User-Agent": UA, "Authorization": f"Basic {auth}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.load(resp)
        self._token = payload["access_token"]
        self._token_exp = time.monotonic() + payload.get("expires_in", 3600)
        return self._token

    def _search(self, symbol):
        q = QUERY_HINTS.get(symbol, f'"${symbol}" OR "{symbol}"')
        url = (f"https://oauth.reddit.com/r/{SUBS}/search.json?"
               + urllib.parse.urlencode({"q": q, "restrict_sr": 1, "sort": "new",
                                         "t": "week", "limit": 50}))
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Authorization": f"Bearer {self._access_token()}"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.load(resp)
        children = (data.get("data") or {}).get("children") or []
        posts, stamps = [], []
        for c in children:
            p = c.get("data") or {}
            ts = p.get("created_utc")
            if ts:
                stamps.append(ts)
            posts.append({
                "id": p.get("id"),
                "body": (p.get("title") or "").strip(),
                "user": p.get("author") or "unknown",
                "likes": p.get("score", 0),
                "created_utc": None if not ts else time.strftime(
                    "%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(ts)),
                "url": "https://www.reddit.com" + (p.get("permalink") or ""),
            })
        rate = round(len(stamps) / 7, 1) if stamps else 0.0  # posts over t=week
        return symbol, {
            "watchers": None,  # no per-symbol follower concept on Reddit
            "post_rate_per_day": rate,
            "sample_size": len(posts),
            "posts": posts[:30],
        }

    def activity(self, symbols):
        out = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            for sym, payload in pool.map(self._safe, symbols):
                if payload is not None:
                    out[sym] = payload
        return out

    def _safe(self, sym):
        try:
            return self._search(sym)
        except Exception:
            return sym, None
