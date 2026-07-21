"""CRPT Tracker API — stage 1.

Serves the frontend and exposes the data spine loaded by loader.py.
Run:  python3 -m uvicorn main:app --port 8642   (from backend/)

Data honesty: if the DB hasn't been built yet, endpoints answer 503 with an
instruction, never an empty-but-plausible payload.
"""
import json
import sqlite3
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import db
import marketdata
import newsdata
import socialdata
from newsdata import quality, signals
from socialdata import wiki

ADAPTER = marketdata.get_adapter()
NEWS = newsdata.get_adapter()
SOCIAL = socialdata.get_adapter()

# Tiny in-process TTL cache so an open dashboard doesn't hammer the provider.
_CACHE: dict = {}


def _cached(key, ttl_seconds, fn):
    hit = _CACHE.get(key)
    if hit and hit[0] > time.monotonic():
        return hit[1]
    value = fn()
    _CACHE[key] = (time.monotonic() + ttl_seconds, value)
    return value


def _now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

FRONTEND = db.DB_PATH.parent.parent / "frontend"

app = FastAPI(title="CRPT Tracker", docs_url=None, redoc_url=None)


def query(sql: str, args=()):  # small helper; one connection per request is fine here
    if not db.DB_PATH.exists():
        raise HTTPException(503, "Database not built. Run: python3 backend/loader.py")
    conn = db.connect()
    try:
        return [dict(r) for r in conn.execute(sql, args).fetchall()]
    except sqlite3.OperationalError as e:
        raise HTTPException(503, f"Database not usable ({e}). Re-run backend/loader.py")
    finally:
        conn.close()


@app.get("/api/health")
def health():
    meta = {r["key"]: r["value"] for r in query("SELECT key, value FROM meta")}
    return {"status": "ok", "loaded_at_utc": meta.get("loaded_at_utc")}


@app.get("/api/meta")
def meta():
    """Load provenance + validation facts, plus the never-price list."""
    out = {r["key"]: r["value"] for r in query("SELECT key, value FROM meta")}
    unpriceable = query(
        "SELECT COALESCE(ticker, name) AS t FROM holdings WHERE priceable = 0 ORDER BY t"
    )
    out["unpriceable_tickers"] = ", ".join(r["t"] for r in unpriceable)
    return out


@app.get("/api/fund")
def fund():
    """Fund identity facts + the vetted HISTORICAL reference snapshots.

    Everything here is point-in-time from crpt_data.json. The frontend must
    render each block with its as-of date; nothing in this payload is live.
    """
    rows = query("SELECT * FROM fund")
    if not rows:
        raise HTTPException(503, "Fund facts missing. Re-run backend/loader.py")
    snapshots = {}
    for r in query(
        "SELECT name, as_of, payload FROM reference_snapshots "
        "WHERE name IN ('current_fund_data','fund_characteristics','performance_snapshot')"
    ):
        snapshots[r["name"]] = {"as_of": r["as_of"], **json.loads(r["payload"])}
    meta = {r["key"]: r["value"] for r in query("SELECT key, value FROM meta")}
    return {
        "fund": rows[0],
        "fund_facts_as_of": meta.get("fund_facts_as_of"),
        **snapshots,
    }


@app.get("/api/holdings")
def holdings():
    """The vetted holdings snapshot + exposure buckets, straight from the DB.

    Weights/values are the official file's point-in-time numbers; the only
    computed figure is top-10 concentration, derived from those same weights."""
    rows = query("SELECT * FROM holdings ORDER BY weight_pct DESC, ticker")
    if not rows:
        raise HTTPException(503, "Holdings missing. Re-run backend/loader.py")
    members: dict = {}
    for m in query("SELECT bucket_key, ticker FROM exposure_bucket_members"):
        members.setdefault(m["bucket_key"], []).append(m["ticker"])
    buckets = [
        {**b, "tickers": members.get(b["bucket_key"], [])}
        for b in query(
            "SELECT bucket_key, label, approx_weight_pct FROM exposure_buckets "
            "ORDER BY approx_weight_pct DESC"
        )
    ]
    ticker_bucket = {t: b["bucket_key"] for b in buckets for t in b["tickers"]}
    for r in rows:
        r["bucket_key"] = ticker_bucket.get(r["ticker"])
    top10 = round(sum(r["weight_pct"] or 0 for r in rows[:10]), 2)
    return {
        "as_of": rows[0]["as_of"],
        "count_securities": sum(1 for r in rows if r["classification"] != "Cash"),
        "top10_weight_pct": top10,
        "line_items": rows,
        "buckets": buckets,
    }


@app.get("/api/quote")
def quote():
    """Delayed live price for CRPT from the market-data adapter."""
    try:
        quotes = _cached("quote:CRPT", 60, lambda: ADAPTER.quote(["CRPT"]))
    except Exception as e:  # provider down entirely
        raise HTTPException(502, f"market data unavailable ({e})")
    q = quotes.get("CRPT")
    if not q:
        raise HTTPException(502, "market data unavailable for CRPT")
    change = change_pct = None
    if q.get("prev_close"):
        change = round(q["price"] - q["prev_close"], 4)
        change_pct = round(change / q["prev_close"] * 100, 2)
    return {
        "symbol": "CRPT",
        **q,
        "change": change,
        "change_pct": change_pct,
        "source": ADAPTER.source_label,
        "fetched_at_utc": _now_utc(),
    }


CHART_RANGES = ("1W", "1M", "3M", "YTD", "1Y")


@app.get("/api/chart")
def chart(range: str = "1M"):
    """Cumulative-return series for CRPT vs its configured benchmarks.

    Returns are computed here from each symbol's own price series
    (close[i]/close[0] - 1), never taken from static snapshot numbers.
    A symbol the provider can't serve comes back with an error field —
    the frontend renders it as "no data"."""
    if range not in CHART_RANGES:
        raise HTTPException(400, f"range must be one of {CHART_RANGES}")
    benches = query("SELECT ticker, label FROM benchmarks ORDER BY rank")
    symbols = [("CRPT", "the fund")] + [(b["ticker"], b["label"]) for b in benches]

    series = []
    for sym, label in symbols:
        try:
            h = _cached(f"hist:{sym}:{range}", 300, lambda s=sym: ADAPTER.history(s, range))
            base = h["closes"][0]
            # [timestamp, price, cumulative return %] — price mode and compare
            # mode read the same series, so the two views can never disagree.
            points = [
                [t, round(c, 4), round((c / base - 1) * 100, 3)]
                for t, c in zip(h["timestamps"], h["closes"])
            ]
            series.append({"symbol": sym, "label": label, "points": points})
        except Exception as e:
            series.append({"symbol": sym, "label": label, "points": [], "error": str(e)})

    return {
        "range": range,
        "source": ADAPTER.source_label,
        "fetched_at_utc": _now_utc(),
        "series": series,
    }


@app.get("/api/news")
def news():
    """Headline feed across every real holding ticker (cash and any untickered
    line never reach the news adapter, same rule as pricing). Filtering by
    ticker happens client-side; this returns the deduped superset."""
    rows = query(
        "SELECT ticker, name FROM holdings WHERE priceable = 1 ORDER BY weight_pct DESC"
    )
    tickers = [r["ticker"] for r in rows]
    names = {r["ticker"]: r["name"] for r in rows}
    try:
        raw = _cached("news:all", 300, lambda: NEWS.news(tickers, names))
    except Exception as e:
        raise HTTPException(502, f"news unavailable ({e})")
    items, dropped = quality.clean(raw)
    for item in items:
        item["signal"] = signals.classify(item.get("headline"), item.get("summary"))
    return {
        "source": NEWS.source_label,
        "adapter": NEWS.name,
        "fetched_at_utc": _now_utc(),
        "tickers": tickers,
        "signals": [{"key": k, "label": lbl} for k, lbl in signals.SIGNALS],
        "quality_filtered": dropped,
        "items": items,
    }


@app.get("/api/social")
def social():
    """Social-activity snapshot per holding from the social adapter.

    A symbol the provider doesn't cover is simply absent (e.g. Tokyo-listed
    Metaplanet on Stocktwits) — the UI renders "no data", never a fake zero.
    Post rates are estimates from the latest message sample, labeled as such."""
    rows = query(
        "SELECT ticker, name, weight_pct FROM holdings WHERE priceable = 1 ORDER BY weight_pct DESC"
    )
    symbols = [r["ticker"] for r in rows]
    try:
        activity = _cached("social:all", 600, lambda: SOCIAL.activity(symbols))
    except Exception as e:
        raise HTTPException(502, f"social data unavailable ({e})")
    # Day price change per holding for the finance-standard red/green tiles.
    # Quotes may fail independently of social data — each falls back to None.
    try:
        quotes = _cached("quotes:holdings", 60, lambda: ADAPTER.quote(symbols))
    except Exception:
        quotes = {}

    def change_pct(sym):
        q = quotes.get(sym)
        if not q or not q.get("prev_close"):
            return None
        return round((q["price"] - q["prev_close"]) / q["prev_close"] * 100, 2)

    return {
        "source": SOCIAL.source_label,
        "adapter": SOCIAL.name,
        "price_source": ADAPTER.source_label,
        "fetched_at_utc": _now_utc(),
        "holdings": [
            {"ticker": r["ticker"], "name": r["name"], "weight_pct": r["weight_pct"],
             **(activity.get(r["ticker"]) or {"watchers": None, "post_rate_per_day": None,
                                              "sample_size": 0, "posts": []}),
             "covered": r["ticker"] in activity,
             "price": (quotes.get(r["ticker"]) or {}).get("price"),
             "change_pct": change_pct(r["ticker"])}
            for r in rows
        ],
    }


@app.get("/api/wiki")
def wiki_attention():
    """Wikipedia-pageview attention per holding (official Wikimedia API).
    Holdings without a verified article are absent -> UI shows "no article"."""
    rows = query("SELECT ticker FROM holdings WHERE priceable = 1 ORDER BY weight_pct DESC")
    symbols = [r["ticker"] for r in rows]
    try:
        data = _cached("wiki:all", 3 * 3600, lambda: wiki.attention(symbols))
    except Exception as e:
        raise HTTPException(502, f"wiki attention unavailable ({e})")
    return {
        "source": "Wikimedia pageviews API (official, daily article reads)",
        "fetched_at_utc": _now_utc(),
        "attention": data,
    }


# Frontend. index.html at /, assets under their SURF-style paths.
@app.get("/", include_in_schema=False)
def index():
    return FileResponse(FRONTEND / "index.html")


app.mount("/css", StaticFiles(directory=FRONTEND / "css"), name="css")
app.mount("/js", StaticFiles(directory=FRONTEND / "js"), name="js")
