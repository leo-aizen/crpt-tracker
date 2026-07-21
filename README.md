# CRPT Tracker

Internal SkyBridge tool for monitoring the CRPT ETF (First Trust SkyBridge Crypto
Industry and Digital Economy ETF). Visual sibling of the Surf Tracker.

**Source of truth:** `data/crpt_data.json` (vetted 2026-07-17 snapshot). When any
external source disagrees on holdings/weights/net assets, the file wins — see its
`source_conflicts` block. Live prices come from a market-data adapter (stage 3),
never from the file.

## Run

```bash
pip install -r requirements.txt          # fastapi + uvicorn (once)
cd backend
python3 loader.py                        # validate + load the snapshot into SQLite
python3 -m uvicorn main:app --port 8642  # serve API + app
# open http://127.0.0.1:8642
```

The loader fails loudly (and writes nothing) if weights don't sum to ~100%, the
security count doesn't match the file's own count, or any line is missing a weight.

## Layout

```
data/crpt_data.json    vetted snapshot (authoritative)
backend/db.py          SQLite schema (rebuilt on every load)
backend/loader.py      validate + ingest the snapshot
backend/main.py        FastAPI: /api/{health,meta,fund,holdings,quote,chart,news}, serves frontend/
backend/marketdata/    swappable price adapters (yahoo | bloomberg later), env CRPT_MARKETDATA
backend/newsdata/      swappable news adapters, env CRPT_NEWS (default "multi":
                       Yahoo + Google News + WSJ/CNBC/MarketWatch/CoinDesk/
                       Cointelegraph/The Block + SEC EDGAR, deduped)
backend/socialdata/    swappable social adapters, env CRPT_SOCIAL (default
                       "stocktwits", keyless; "reddit" ready — create a free
                       script app at reddit.com/prefs/apps and set
                       CRPT_REDDIT_CLIENT_ID / CRPT_REDDIT_CLIENT_SECRET)
frontend/index.html    app shell (SURF-matched: dark, pinned toolbar, cards)
frontend/css/surf-styles.css   SURF visual baseline, reused as-is
frontend/css/crpt.css  CRPT-specific components on SURF variables
frontend/js/app.js     tabs + provenance card
```

## Build stages (pause for review after each)

1. **done** — shell + SURF styling + loader with validation + data-spine API
2. **done** — Overview: fund facts, historical fund-data snapshot, performance &
   risk snapshot, portfolio characteristics — every block labeled with its as-of
   date, snapshot cards chipped "historical · not live"
3. **done** — market-data adapter (`backend/marketdata/`, Yahoo placeholder,
   select via `CRPT_MARKETDATA` env var, Bloomberg DAPI later) + live CRPT price
   card (60s refresh) + cumulative-return chart vs IBIT/BITQ/SPY over
   1W/1M/3M/YTD/1Y, computed from the adapter's price series
4. **done** — Holdings view: exposure-bucket composition bar + legend ("what
   CRPT structurally is"), full 19+cash table with weight bars colored by
   bucket, By-weight / By-bucket grouping toggle, not-priceable chips,
   top-10 concentration computed from official weights
5. **done** — news adapter package (`backend/newsdata/`, select via `CRPT_NEWS`
   env var): `yahoo_rss` default (real per-holding headlines, deduped across
   tickers) + `stub` (intentionally empty — the honest no-provider state);
   card feed UI with per-ticker filter chips, counts, and refresh

All five stages complete.

Post-stage additions:
- **v0.8.x** — News controls reorganized: searchable holdings picker dropdown
  (ticker, name, weight, story count) replaces the ticker chip wall; signal
  chips collapse behind a "Filters ▾" disclosure. (A flagged "Major news" tab
  was built in v0.8.0 and removed in v0.8.1 at Leo's call — see git-less
  history in memory if it ever needs resurrecting.)
- **v0.7.0** — chart defaults to CRPT-only price view in dollars (1W window uses
  30-minute intraday bars) with a "vs benchmarks (%)" compare toggle; delay is
  stated explicitly as ~15 minutes everywhere; holdings note fields (internal
  build guidance) no longer render in the UI; News gained an **AI PROMPT**
  button that copies a paste-ready briefing prompt built from the currently
  filtered items + fund weights — no API key, the user pastes it into their AI
  of choice (SURF pattern).
- **News signals** (v0.6.0) — every item is auto-tagged by keyword rules
  (`backend/newsdata/signals.py`) into desk-relevant signals: BTC treasury,
  Regulatory, Analyst action, Deals & capital, Earnings, Leadership,
  Mining & infra, General. Feed filters combine holding × signal × free-text
  search. Tags are labeled heuristic in the UI; an AI classifier can replace
  `signals.classify()` behind the same signature later.

## Gotchas honored in code

- `$USD` cash line and any untickered line (e.g. the "Ft Sky Crypt Cym" Cayman
  feeder if it ever appears) are forced `priceable = 0` and never reach the
  price adapter (`loader.normalize_line`).
- Metaplanet is `3350.JP` — non-US symbol; the Yahoo adapter maps it to `3350.T`
  (`marketdata/yahoo.py` SYMBOL_MAP; Bloomberg will use `3350 JP Equity`).
  Mapping verified working against the live endpoint.
- ASST's odd "Health Care Equipment & Supplies" classification is the fund's own
  tag — displayed as-is.
- Missing values render as "no data", never a guess; every figure carries its
  as-of date.
