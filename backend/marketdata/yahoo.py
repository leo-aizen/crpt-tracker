"""Placeholder provider: Yahoo Finance's public chart endpoint.

Free, no key, delayed — good enough for an internal monitor until the
Bloomberg DAPI adapter exists. Unofficial API, so failures are expected
occasionally; callers must surface "no data", not retry into a guess.
"""
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from .base import MarketDataAdapter

# Our canonical ticker -> Yahoo symbol. Everything else passes through.
SYMBOL_MAP = {"3350.JP": "3350.T"}

# range -> (provider range, bar interval). 1W uses 30-minute bars so the
# short window shows real intraday shape instead of five daily points.
RANGE_MAP = {
    "1W": ("5d", "30m"),
    "1M": ("1mo", "1d"),
    "3M": ("3mo", "1d"),
    "YTD": ("ytd", "1d"),
    "1Y": ("1y", "1d"),
}

UA = "Mozilla/5.0 (internal CRPT tracker; contact: SkyBridge research)"


def _fetch_chart(symbol: str, rng: str, interval: str) -> dict:
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(symbol)}?range={rng}&interval={interval}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as resp:
        payload = json.load(resp)
    result = (payload.get("chart") or {}).get("result")
    if not result:
        err = ((payload.get("chart") or {}).get("error") or {}).get("description")
        raise RuntimeError(err or f"no chart data for {symbol}")
    return result[0]


class YahooAdapter(MarketDataAdapter):
    name = "yahoo"
    source_label = "Yahoo Finance (free feed, ~15 min delayed)"

    def quote(self, symbols):
        out = {}
        with ThreadPoolExecutor(max_workers=8) as pool:
            for our_sym, q in pool.map(self._quote_one, symbols):
                if q is not None:
                    out[our_sym] = q
        return out

    @staticmethod
    def _quote_one(our_sym):
        ysym = SYMBOL_MAP.get(our_sym, our_sym)
        try:
            meta = _fetch_chart(ysym, "1d", "1d")["meta"]
            price = meta.get("regularMarketPrice")
            if price is None:
                return our_sym, None
            mtime = meta.get("regularMarketTime")
            return our_sym, {
                "price": price,
                "prev_close": meta.get("chartPreviousClose") or meta.get("previousClose"),
                "currency": meta.get("currency"),
                "market_time_utc": (
                    datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(timespec="seconds")
                    if mtime else None
                ),
            }
        except Exception:
            return our_sym, None  # absent symbol == "no data" downstream

    def history(self, symbol, rng):
        if rng not in RANGE_MAP:
            raise ValueError(f"unsupported range {rng!r}")
        ysym = SYMBOL_MAP.get(symbol, symbol)
        yrange, interval = RANGE_MAP[rng]
        result = _fetch_chart(ysym, yrange, interval)
        stamps = result.get("timestamp") or []
        quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        closes = quotes.get("close") or []
        ts_out, px_out = [], []
        for t, c in zip(stamps, closes):
            if c is not None:
                ts_out.append(t)
                px_out.append(c)
        if len(px_out) < 2:
            raise RuntimeError(f"not enough price history for {symbol} over {rng}")
        return {
            "timestamps": ts_out,
            "closes": px_out,
            "currency": (result.get("meta") or {}).get("currency"),
        }
